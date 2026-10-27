from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from app.config import JOB_DIR, ROOT
from app.subprocess_utils import run_hidden
from app.db import get_match, init_db, list_clip_rejections, list_clips, update_match


def log(message: str) -> None:
    print(message, flush=True)


def run(command: list[str], log_file) -> None:
    log("$ " + " ".join(command))
    run_hidden(
        command,
        cwd=str(ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        check=True,
    )


def update_progress(match_id: int, progress: float, message: str) -> None:
    update_match(match_id, progress=progress, message=message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", type=int, required=True)
    parser.add_argument("--threshold", type=float, default=0.03)
    parser.add_argument("--min-score", type=float, default=50.0)
    parser.add_argument("--max-clips", type=int, default=100)
    parser.add_argument("--reuse-detections", action="store_true")
    args = parser.parse_args()

    init_db()
    match = get_match(args.match_id)
    if match is None:
        print("partida não encontrada")
        return 1
    video_path = Path(match["video_path"])
    if not video_path.is_file():
        print("vídeo não encontrado")
        return 1
    if not match["calibration"]:
        update_match(args.match_id, status="error", message="Calibre a quadra antes de gerar os clipes")
        return 1

    job_dir = JOB_DIR / f"match-{args.match_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    whistle_mode = match["whistle_mode"] if "whistle_mode" in match.keys() else "with"
    update_match(
        args.match_id,
        status="processing",
        progress=0,
        message="Iniciando análise de bola...",
        result=None,
        annotated_path=None,
    )

    with (job_dir / "clip_job.log").open("a", encoding="utf-8") as log_file:
        try:
            log("=== VolleyTrak clip job ===")
            reuse = args.reuse_detections
            ball_path = job_dir / "ball_vballnet.jsonl"
            track_path = job_dir / "ball_track.jsonl"
            contacts_path = job_dir / "contacts.json"
            activity_path = job_dir / "activity.json"
            rallies_path = job_dir / "rallies_audio.json"
            points_path = job_dir / "points.json"

            reused_ball = bool(reuse and ball_path.is_file())
            if reused_ball:
                log("reutilizando detecção de bola existente")
                update_progress(
                    args.match_id, 30, "Reutilizando detecção de bola existente..."
                )
            else:
                update_progress(args.match_id, 5, "Analisando a bola em 30 fps...")
                run(
                    [
                        sys.executable,
                        "-m",
                        "pipeline.vballnet",
                        "--match-id",
                        str(args.match_id),
                        "--threshold",
                        "0.4",
                    ],
                    log_file,
                )

            reused_track = bool(reuse and track_path.is_file())
            if reused_track:
                log("reutilizando trajetória tratada da bola")
                update_progress(
                    args.match_id, 32, "Reutilizando trajetória da bola..."
                )
            else:
                update_progress(args.match_id, 30, "Tratando trajetória da bola...")
                run(
                    [
                        sys.executable,
                        "-m",
                        "pipeline.ball_track",
                        "--match-id",
                        str(args.match_id),
                    ],
                    log_file,
                )

            reused_contacts = bool(
                reuse and reused_track and contacts_path.is_file()
            )
            if reused_contacts:
                log("reutilizando contatos existentes")
                update_progress(
                    args.match_id, 55, "Reutilizando contatos existentes..."
                )
            else:
                update_progress(args.match_id, 50, "Detectando contatos...")
                run(
                    [
                        sys.executable,
                        "-m",
                        "pipeline.contacts",
                        "--match-id",
                        str(args.match_id),
                        "--input",
                        "ball_track.jsonl",
                        "--output",
                        "contacts.json",
                    ],
                    log_file,
                )

            if whistle_mode == "with":
                if (
                    reuse
                    and reused_ball
                    and reused_contacts
                    and rallies_path.is_file()
                ):
                    log("reutilizando apitos e rallies existentes")
                    update_progress(
                        args.match_id, 78, "Reutilizando apitos e rallies existentes..."
                    )
                else:
                    update_progress(args.match_id, 60, "Detectando apitos...")
                    run(
                        [
                            sys.executable,
                            "-m",
                            "pipeline.audio",
                            "--match-id",
                            str(args.match_id),
                            "--threshold",
                            str(args.threshold),
                        ],
                        log_file,
                    )

                    update_progress(args.match_id, 78, "Montando rallies por apito...")
                    run(
                        [
                            sys.executable,
                            "-m",
                            "pipeline.rallies",
                            "--match-id",
                            str(args.match_id),
                            "--ball",
                            "ball_track.jsonl",
                            "--contacts",
                            "contacts.json",
                            "--output",
                            "rallies_audio.json",
                        ],
                        log_file,
                    )
            else:
                (job_dir / "whistles.json").unlink(missing_ok=True)
                rallies_path.unlink(missing_ok=True)
                update_progress(
                    args.match_id,
                    70,
                    "Modo sem apito: usando bola e contatos...",
                )

            if reuse and activity_path.is_file():
                log("reutilizando atividade visual existente")
                update_progress(
                    args.match_id, 82, "Reutilizando atividade visual da quadra..."
                )
            else:
                update_progress(
                    args.match_id, 82, "Medindo atividade visual da quadra..."
                )
                run(
                    [
                        sys.executable,
                        "-m",
                        "pipeline.activity",
                        "--match-id",
                        str(args.match_id),
                    ],
                    log_file,
                )

            if reuse and points_path.is_file():
                log("recalculando pontos a partir das detecções atuais")
            update_progress(args.match_id, 86, "Montando pontos e rallies...")
            run(
                [
                    sys.executable,
                    "-m",
                    "pipeline.points",
                    "--match-id",
                    str(args.match_id),
                ],
                log_file,
            )

            update_progress(args.match_id, 90, "Cortando clipes...")
            clips_command = [
                sys.executable,
                "-m",
                "pipeline.clips",
                "--match-id",
                str(args.match_id),
                "--min-score",
                str(args.min_score),
                "--max-clips",
                str(args.max_clips),
            ]
            if whistle_mode == "without":
                clips_command.append("--no-audio")
            run(clips_command, log_file)

            ball_meta = json.loads((job_dir / "ball_vballnet.json").read_text(encoding="utf-8"))
            contacts = json.loads((job_dir / "contacts.json").read_text(encoding="utf-8"))
            rallies = (
                json.loads((job_dir / "rallies_audio.json").read_text(encoding="utf-8"))
                if whistle_mode == "with" and (job_dir / "rallies_audio.json").is_file()
                else []
            )
            clips = list_clips(args.match_id)
            fps = float(ball_meta.get("fps") or 30.0)
            duration = float(ball_meta.get("frames") or 0) / fps
            calibration = json.loads(match["calibration"]) if match["calibration"] else {}
            summary = {
                "frames_total": ball_meta.get("frames"),
                "frames_processed": ball_meta.get("frames"),
                "fps": ball_meta.get("fps"),
                "stride": 1,
                "duration_s": round(duration, 1),
                "persons_detected": 0,
                "unique_person_tracks": 0,
                "tentative_touches": 0,
                "ball_detected": ball_meta.get("frames_with_ball"),
                "ball_visibility_pct": ball_meta.get("ball_frame_pct"),
                "ball_detection_pct": ball_meta.get("ball_frame_pct"),
                "detector": "vballnet (clipes)",
                "ball_model": "vballnet 30 fps",
                "calibrated": True,
                "calibration_mode": calibration.get("mode", "full"),
                "elapsed_s": round(time.time() - started, 1),
                "audio_whistles": (
                    len(json.loads((job_dir / "whistles.json").read_text(encoding="utf-8")))
                    if whistle_mode == "with" and (job_dir / "whistles.json").is_file()
                    else 0
                ),
                "whistle_mode": whistle_mode,
                "audio_rallies": len(rallies),
                "contacts": len(contacts),
                "clips": len(clips),
                "clips_new": sum(1 for clip in clips if clip["status"] == "new"),
                "clips_saved": sum(1 for clip in clips if clip["status"] == "saved"),
                "clips_rejected": len(list_clip_rejections(args.match_id)),
                "clips_starred": sum(1 for clip in clips if clip["starred"]),
                "clips_gap": sum(1 for clip in clips if clip["source"] == "gap"),
                "clips_point": sum(1 for clip in clips if clip["source"] == "point"),
                "clips_recovered": sum(
                    1 for clip in clips if clip["source"] == "recovered"
                ),
                "clips_manual": sum(
                    1 for clip in clips if clip["source"] == "manual"
                ),
            }
            result = {
                "summary": summary,
                "warnings": [
                    "Atividade visual da quadra aplicada: trechos vazios/parados foram descartados.",
                    "Fluxo focado em clipes: sem pipeline de pessoas e sem vídeo anotado.",
                    "Trajetória da bola tratada e pontos montados por saque/fim de ponto.",
                    (
                        "Modo sem apito: a segmentação usou bola, contatos e atividade visual."
                        if whistle_mode == "without"
                        else "Áudio, VballNet, contatos e o perfil/ranker aprendidos foram aplicados."
                    ),
                    "Clipes salvos e rejeições anteriores foram preservados; revise os novos.",
                ],
                "files": {
                    "ball_vballnet": "ball_vballnet.jsonl",
                    "ball_track": "ball_track.jsonl",
                    "whistles": "whistles.json",
                    "contacts": "contacts.json",
                    "rallies_audio": "rallies_audio.json",
                    "activity": "activity.json",
                    "points": "points.json",
                    "log": "clip_job.log",
                },
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            update_match(
                args.match_id,
                status="done",
                progress=100,
                message=f"{len(clips)} clipes gerados",
                result=json.dumps(result, ensure_ascii=False),
                annotated_path=None,
            )
            log(f"=== concluído em {summary['elapsed_s']}s: {len(clips)} clipes ===")
            return 0
        except Exception as exc:
            traceback.print_exc()
            log_file.write(f"\nERRO: {type(exc).__name__}: {exc}\n")
            update_match(
                args.match_id,
                status="error",
                message=f"Falha na geração de clipes: {type(exc).__name__}: {exc}"[:500],
            )
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
