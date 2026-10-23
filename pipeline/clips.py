from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np

from app.config import JOB_DIR
from app.db import (
    add_clip,
    clear_unreviewed_clips,
    get_match,
    init_db,
    list_clip_rejections,
    list_clips,
)
from pipeline.clips_core import select_balls, windows_from_ball
from pipeline.feedback import build_profile_for_match
from pipeline.ranker import feature_vector, predict_probability, train_and_save


def trim_dead_time(
    windows: list[dict],
    records: list[dict],
    contact_times: list[float],
    active_speed: float = 2.5,
    pre_roll: float = 1.0,
    post_roll: float = 1.8,
) -> tuple[list[dict], int]:
    trimmed = 0
    for window in windows:
        samples: list[tuple[float, list[float]]] = []
        for record in records:
            if record["t"] < window["start"] or record["t"] > window["end"]:
                continue
            balls = select_balls(record)
            if not balls:
                continue
            ball = max(balls, key=lambda item: item.get("score", 0.0))
            samples.append((float(record["t"]), ball["court"]))
        if not samples:
            continue

        active = []
        for index, (sample_time, _) in enumerate(samples):
            if any(abs(sample_time - contact) <= 0.45 for contact in contact_times):
                active.append(sample_time)
                continue
            if index == 0:
                continue
            previous_time, previous_court = samples[index - 1]
            gap = sample_time - previous_time
            if gap <= 0 or gap > 0.25:
                continue
            _, court = samples[index]
            speed = math.hypot(
                court[0] - previous_court[0], court[1] - previous_court[1]
            ) / gap
            if 0 < speed <= 45.0 and speed >= active_speed:
                active.append(sample_time)
                active.append(previous_time)
        if not active:
            continue

        first_active = min(active)
        last_active = max(active)
        new_start = max(window["start"], first_active - pre_roll)
        new_end = min(window["end"], last_active + post_roll)
        if new_end - new_start < 3.0:
            new_end = min(window["end"], new_start + 3.0)
        if new_end - new_start < 2.0:
            continue
        if new_start > window["start"] + 0.4 or new_end < window["end"] - 0.4:
            trimmed += 1
        window["original_start"] = window["start"]
        window["original_end"] = window["end"]
        window["start"] = round(new_start, 2)
        window["end"] = round(new_end, 2)
        window["duration"] = round(new_end - new_start, 2)
    return windows, trimmed


def split_long_windows(
    windows: list[dict],
    records: list[dict],
    max_duration: float = 20.0,
    max_parts: int = 3,
) -> tuple[list[dict], int]:
    result: list[dict] = []
    split_count = 0
    for original in windows:
        queue = [dict(original)]
        parts = 1
        while queue:
            window = queue.pop(0)
            duration = float(window["end"]) - float(window["start"])
            if duration <= max_duration or parts >= max_parts:
                result.append(window)
                continue

            samples = []
            for record in records:
                if window["start"] <= record["t"] <= window["end"]:
                    balls = select_balls(record)
                    if balls:
                        samples.append((float(record["t"]), balls[0]["court"]))
            split_time = (float(window["start"]) + float(window["end"])) / 2.0
            if len(samples) >= 3:
                speeds = []
                for (t0, p0), (t1, p1) in zip(samples, samples[1:]):
                    gap = t1 - t0
                    if gap <= 0 or gap > 0.3:
                        continue
                    speed = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / gap
                    if 0 < speed <= 45:
                        speeds.append((speed, (t0 + t1) / 2.0))
                middle = [item for item in speeds if window["start"] + duration * 0.25 <= item[1] <= window["end"] - duration * 0.25]
                if middle:
                    split_time = min(middle, key=lambda item: item[0])[1]

            if split_time - window["start"] < 3.0 or window["end"] - split_time < 3.0:
                split_time = (float(window["start"]) + float(window["end"])) / 2.0

            left = dict(window)
            right = dict(window)
            left["end"] = round(split_time, 2)
            left["duration"] = round(split_time - float(window["start"]), 2)
            right["start"] = round(split_time, 2)
            right["duration"] = round(float(window["end"]) - split_time, 2)
            queue.extend([left, right])
            parts += 1
            split_count += 1
    return result, split_count


def cut_clip(video_path: Path, start: float, end: float, output_path: Path) -> bool:
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start:.2f}",
        "-to",
        f"{end:.2f}",
        "-i",
        str(video_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=300)
        return output_path.is_file() and output_path.stat().st_size > 0
    except Exception as exc:
        print(f"[aviso] falha ao cortar {start:.1f}-{end:.1f}: {exc}")
        output_path.unlink(missing_ok=True)
        return False


def make_thumb(clip_path: Path, thumb_path: Path, seek: float = 1.5) -> bool:
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{seek:.2f}",
        "-i",
        str(clip_path),
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(thumb_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=60)
        return thumb_path.is_file()
    except Exception:
        thumb_path.unlink(missing_ok=True)
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", type=int, required=True)
    parser.add_argument("--threshold", type=float, default=3.0)
    parser.add_argument("--min-y", type=float, default=300.0)
    parser.add_argument("--min-score", type=float, default=50.0)
    parser.add_argument("--max-clips", type=int, default=60)
    parser.add_argument("--ball", default="")
    parser.add_argument("--rallies", default="")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--preview", action="store_true")
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
    job_dir = JOB_DIR / f"match-{args.match_id}"
    ball_path = job_dir / (args.ball or "ball_vballnet.jsonl")
    if not args.ball and not ball_path.is_file():
        ball_path = job_dir / "ball_dfine.jsonl"
    if not ball_path.is_file():
        print("passagem de bola não encontrada; rode pipeline.vballnet ou ball_pass primeiro")
        return 1
    print(f"track={ball_path.name}")

    calibration = json.loads(match["calibration"]) if match["calibration"] else {}
    mode = calibration.get("mode", "full")
    min_y = None if mode == "full" else args.min_y
    net_x = {"full": 9.0, "center": 9.0, "near_attack": 12.0, "far_attack": 6.0}.get(
        mode, 9.0
    )
    print(f"modo={mode} net_x={net_x} min_y={min_y}")
    feedback_profile = build_profile_for_match(args.match_id)
    trim_profile = feedback_profile.get("trim", {})
    min_ball_pct = float(feedback_profile.get("min_ball_pct", 0.10))
    ranker_model = train_and_save()
    ranker_auc = float(ranker_model.get("cv_auc") or 0.0)
    ranker_weight = 0.2 if ranker_auc >= 0.55 else 0.0
    print(
        f"aprendizado: pre_roll={trim_profile.get('pre_roll', 1.0)}s "
        f"post_roll={trim_profile.get('post_roll', 1.8)}s "
        f"active_speed={trim_profile.get('active_speed', 2.5)} "
        f"min_ball_pct={min_ball_pct} ranker_auc={ranker_auc:.3f} "
        f"ranker_peso={ranker_weight}"
    )

    speed_windows = windows_from_ball(
        ball_path,
        threshold=args.threshold,
        min_y=min_y,
        min_score=args.min_score,
        max_clips=args.max_clips,
        net_x=net_x,
    )

    audio_windows: list[dict] = []
    rallies_path = job_dir / (args.rallies or "rallies_audio.json")
    if not args.no_audio and rallies_path.is_file():
        for rally in json.loads(rallies_path.read_text(encoding="utf-8")):
            if float(rally.get("score", 0.0)) < args.min_score:
                continue
            if float(rally.get("ball_pct", 0.0)) < min_ball_pct:
                continue
            audio_windows.append(
                {
                    "start": float(rally["start"]),
                    "end": float(rally["end"]),
                    "duration": round(float(rally["end"]) - float(rally["start"]), 1),
                    "score": min(100.0, float(rally.get("score", 0.0))),
                    "max_speed": float(rally.get("max_speed", 0.0)),
                    "ball_pct": float(rally.get("ball_pct", 0.0)),
                    "contacts": int(rally.get("contacts", 0)),
                    "whistle_start": rally.get("whistle_start"),
                    "whistle_end": rally.get("whistle_end"),
                    "crossings": 0,
                    "min_y": None,
                    "source": "audio",
                }
            )

    if audio_windows:
        # Com apito disponível, a janela de áudio manda; janelas de velocidade
        # podem se esticar por minutos quando o track erra e viram falsos rallies.
        windows = sorted(audio_windows, key=lambda item: item["start"])
    else:
        for window in speed_windows:
            window["source"] = "speed"
        windows = speed_windows

    rejections = list_clip_rejections(args.match_id)
    if rejections:
        filtered = []
        for window in windows:
            duration = max(0.1, window["end"] - window["start"])
            rejected = False
            for rejection in rejections:
                overlap = max(
                    0.0,
                    min(window["end"], rejection["end"])
                    - max(window["start"], rejection["start"]),
                )
                rejection_duration = max(0.1, rejection["end"] - rejection["start"])
                if overlap / min(duration, rejection_duration) > 0.5:
                    rejected = True
                    break
            if not rejected:
                filtered.append(window)
        print(f"ignorados por rejeição anterior: {len(windows) - len(filtered)}")
        windows = filtered

    records = [
        json.loads(line)
        for line in ball_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    contacts_path = job_dir / "contacts.json"
    contact_times = []
    if contacts_path.is_file():
        contact_times = [
            float(contact["t"])
            for contact in json.loads(contacts_path.read_text(encoding="utf-8"))
        ]
    windows, trimmed_count = trim_dead_time(
        windows,
        records,
        contact_times,
        active_speed=float(trim_profile.get("active_speed", 2.5)),
        pre_roll=float(trim_profile.get("pre_roll", 1.0)),
        post_roll=float(trim_profile.get("post_roll", 1.8)),
    )
    if trimmed_count:
        print(f"tempo morto aparado em {trimmed_count} candidato(s)")

    windows, split_count = split_long_windows(windows, records, max_duration=20.0)
    if split_count:
        print(f"janelas longas divididas: {split_count}")

    if ranker_weight > 0:
        for window in windows:
            window["base_score"] = window["score"]
            vector = feature_vector(
                window,
                float(window["duration"]),
                str(window.get("source", "speed")),
            )
            probability = predict_probability(ranker_model, vector)
            window["ranker_score"] = round(probability * 100.0, 1)
            window["score"] = round(
                (1.0 - ranker_weight) * window["score"]
                + ranker_weight * window["ranker_score"],
                1,
            )

    saved_clips = list_clips(args.match_id, "saved")
    if saved_clips:
        filtered = []
        for window in windows:
            duration = max(0.1, window["end"] - window["start"])
            duplicate = False
            for saved in saved_clips:
                overlap = max(
                    0.0,
                    min(window["end"], saved["end"])
                    - max(window["start"], saved["start"]),
                )
                saved_duration = max(0.1, saved["end"] - saved["start"])
                if overlap / min(duration, saved_duration) > 0.5:
                    duplicate = True
                    break
            if not duplicate:
                filtered.append(window)
        print(f"ignorados por já estarem salvos: {len(windows) - len(filtered)}")
        windows = filtered

    windows = windows[: args.max_clips]
    print(f"candidatos: {len(windows)} (audio={len(audio_windows)})")
    for window in windows:
        min_y_value = window.get("min_y")
        min_y_text = "-" if min_y_value is None else f"{min_y_value:.0f}"
        print(
            f"  {window['start']:.1f}-{window['end']:.1f}s "
            f"dur={window['duration']:.1f} score={window['score']:.2f} "
            f"min_y={min_y_text} crossings={window.get('crossings', 0)} "
            f"source={window.get('source', 'speed')} "
            f"ranker={window.get('ranker_score', '-')}"
        )
    if not windows:
        return 0
    if args.preview:
        print("preview: nenhum clipe foi gerado")
        return 0

    clips_dir = JOB_DIR / f"match-{args.match_id}" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    for old in clear_unreviewed_clips(args.match_id):
        Path(old["path"]).unlink(missing_ok=True)
        if old["thumb"]:
            Path(old["thumb"]).unlink(missing_ok=True)
    batch = datetime.now().strftime("%Y%m%d-%H%M%S")

    created = []
    for index, window in enumerate(windows, start=1):
        clip_path = clips_dir / f"rally-{batch}-{index:03d}.mp4"
        thumb_path = clips_dir / f"rally-{batch}-{index:03d}.jpg"
        if not cut_clip(video_path, window["start"], window["end"], clip_path):
            continue
        thumb_seek = min(6.0, max(1.5, window["duration"] * 0.35))
        make_thumb(clip_path, thumb_path, seek=thumb_seek)
        features = {
            key: window.get(key)
            for key in (
                "active_samples",
                "max_speed",
                "min_y",
                "crossings",
                "ball_pct",
                "contacts",
                "whistle_start",
                "whistle_end",
                "ranker_score",
                "original_start",
                "original_end",
            )
            if window.get(key) is not None
        }
        clip_id = add_clip(
            args.match_id,
            start=window["start"],
            end=window["end"],
            duration=window["duration"],
            path=str(clip_path),
            thumb=str(thumb_path) if thumb_path.is_file() else None,
            score=window["score"],
            source=window.get("source", "speed"),
            features=features,
        )
        created.append(
            {
                "id": clip_id,
                "start": window["start"],
                "end": window["end"],
                "duration": window["duration"],
                "score": window["score"],
                "source": window.get("source", "speed"),
                "path": str(clip_path),
            }
        )
        print(f"clipe {index}/{len(windows)} -> {clip_path.name}")

    meta_path = JOB_DIR / f"match-{args.match_id}" / "clips.json"
    meta_path.write_text(json.dumps(created, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"clipes criados: {len(created)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
