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
from app.db import get_match, init_db, list_clip_rejections, list_clips, update_match


def log(message: str) -> None:
    print(message, flush=True)


def run(command: list[str], log_file) -> None:
    log("$ " + " ".join(command))
    subprocess.run(
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

            update_progress(args.match_id, 70, "Detectando contatos...")
            run(
                [
                    sys.executable,
                    "-m",
                    "pipeline.contacts",
                    "--match-id",
                    str(args.match_id),
                    "--input",
                    "ball_vballnet.jsonl",
                    "--output",
                    "contacts.json",
                ],
                log_file,
            )

            update_progress(args.match_id, 78, "Montando rallies...")
            run(
                [
                    sys.executable,
                    "-m",
                    "pipeline.rallies",
                    "--match-id",
                    str(args.match_id),
                    "--ball",
                    "ball_vballnet.jsonl",
                    "--contacts",
                    "contacts.json",
                    "--output",
                    "rallies_audio.json",
                ],
                log_file,
            )

            update_progress(args.match_id, 86, "Cortando clipes...")
            run(
                [
                    sys.executable,
                    "-m",
                    "pipeline.clips",
                    "--match-id",
                    str(args.match_id),
                    "--min-score",
                    str(args.min_score),
                    "--max-clips",
                    str(args.max_clips),
                ],
                log_file,
            )

            ball_meta = json.loads((job_dir / "ball_vballnet.json").read_text(encoding="utf-8"))
            contacts = json.loads((job_dir / "contacts.json").read_text(encoding="utf-8"))
            rallies = json.loads((job_dir / "rallies_audio.json").read_text(encoding="utf-8"))
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
                "audio_whistles": len(json.loads((job_dir / "whistles.json").read_text(encoding="utf-8"))),
                "audio_rallies": len(rallies),
                "contacts": len(contacts),
                "clips": len(clips),
                "clips_new": sum(1 for clip in clips if clip["status"] == "new"),
                "clips_saved": sum(1 for clip in clips if clip["status"] == "saved"),
                "clips_rejected": len(list_clip_rejections(args.match_id)),
                "clips_starred": sum(1 for clip in clips if clip["starred"]),
            }
            result = {
                "summary": summary,
                "warnings": [
                    "Fluxo focado em clipes: sem pipeline de pessoas e sem vídeo anotado.",
                    "Áudio, VballNet, contatos e o perfil/ranker aprendidos foram aplicados.",
                    "Clipes salvos e rejeições anteriores foram preservados; revise os novos.",
                ],
                "files": {
                    "ball_vballnet": "ball_vballnet.jsonl",
                    "whistles": "whistles.json",
                    "contacts": "contacts.json",
                    "rallies_audio": "rallies_audio.json",
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
