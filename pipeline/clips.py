from __future__ import annotations

import argparse
import bisect
import json
import math
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np

from app.clip_paths import clip_dir_for_match
from app.config import JOB_DIR
from app.constants import CLIP_REJECTION_CANONICAL
from app.db import (
    add_clip,
    clear_unreviewed_clips,
    get_match,
    init_db,
    list_clip_rejections,
    list_clips,
)
from pipeline.clips_core import select_balls, windows_from_ball
from pipeline.feedback import build_global_profile, build_profile_for_match
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


def contact_windows(
    contacts: list[dict],
    records: list[dict],
    duration: float,
    max_gap: float = 4.0,
    min_contacts: int = 3,
    max_duration: float = 30.0,
    min_contact_score: float = 150.0,
    min_score: float = 55.0,
    max_group_span: float | None = None,
    pre_pad: float = 2.5,
    post_pad: float = 1.5,
) -> list[dict]:
    points = sorted(
        float(item["t"])
        for item in contacts
        if float(item.get("score", 0.0)) >= min_contact_score
    )
    groups: list[list[float]] = []
    current: list[float] = []
    for point in points:
        if current and (
            point - current[-1] > max_gap
            or (max_group_span is not None and point - current[0] > max_group_span)
        ):
            groups.append(current)
            current = []
        current.append(point)
    if current:
        groups.append(current)

    record_times = [float(record["t"]) for record in records]
    windows: list[dict] = []
    for group in groups:
        if len(group) < min_contacts:
            continue
        start = max(0.0, group[0] - pre_pad)
        end = min(duration, group[-1] + post_pad)
        if end - start < 3.0 or end - start > max_duration:
            continue
        left = bisect.bisect_left(record_times, start)
        right = bisect.bisect_right(record_times, end)
        subset = records[left:right]
        samples = []
        for record in subset:
            balls = select_balls(record)
            if balls:
                samples.append((float(record["t"]), balls[0]["court"]))
        max_speed = 0.0
        for (t0, p0), (t1, p1) in zip(samples, samples[1:]):
            gap = t1 - t0
            if gap <= 0 or gap > 0.3:
                continue
            speed = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / gap
            if 0 < speed <= 45:
                max_speed = max(max_speed, speed)
        ball_pct = len(samples) / max(1, len(subset))
        contact_count = len(group)
        score = round(
            50.0
            + 20.0 * min(1.0, ball_pct / 0.5)
            + 20.0 * min(1.0, contact_count / 5.0)
            + 10.0 * min(1.0, max_speed / 25.0),
            1,
        )
        if score < min_score:
            continue
        windows.append(
            {
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": round(end - start, 2),
                "score": score,
                "max_speed": round(max_speed, 1),
                "ball_pct": round(ball_pct, 3),
                "contacts": contact_count,
                "crossings": 0,
                "min_y": None,
                "source": "contact",
            }
        )
    return windows


def window_stats(
    records: list[dict],
    contact_times: list[float],
    start: float,
    end: float,
) -> dict:
    record_times = [float(record["t"]) for record in records]
    left = bisect.bisect_left(record_times, start)
    right = bisect.bisect_right(record_times, end)
    subset = records[left:right]
    samples = []
    for record in subset:
        balls = select_balls(record)
        if balls:
            samples.append((float(record["t"]), balls[0]["court"]))
    max_speed = 0.0
    for (t0, p0), (t1, p1) in zip(samples, samples[1:]):
        gap = t1 - t0
        if gap <= 0 or gap > 0.3:
            continue
        speed = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / gap
        if 0 < speed <= 45:
            max_speed = max(max_speed, speed)
    contacts = sum(1 for value in contact_times if start <= value <= end)
    return {
        "ball_pct": len(samples) / max(1, len(subset)),
        "max_speed": max_speed,
        "contacts": contacts,
    }


def find_clip_gaps(
    clips: list,
    duration: float,
    min_gap_seconds: float = 60.0,
) -> list[dict]:
    total = max(1, int(math.ceil(duration)))
    covered = bytearray(total)
    for clip in clips:
        start = max(0, int(math.floor(float(clip["start"]))))
        end = min(total, int(math.ceil(float(clip["end"]))))
        for index in range(start, end):
            covered[index] = 1
    gaps: list[dict] = []
    index = 0
    while index < total:
        if covered[index]:
            index += 1
            continue
        start = index
        while index < total and not covered[index]:
            index += 1
        if index - start >= min_gap_seconds:
            gaps.append(
                {
                    "start": float(start),
                    "end": float(index),
                    "duration": float(index - start),
                }
            )
    return gaps


def gap_windows(
    gaps: list[dict],
    contacts: list[dict],
    records: list[dict],
    duration: float,
    max_total: int = 24,
    max_per_gap: int = 3,
    min_ball_pct: float = 0.08,
) -> list[dict]:
    if not gaps or max_total <= 0 or not contacts:
        return []
    relaxed = contact_windows(
        contacts,
        records,
        duration,
        max_gap=5.0,
        min_contacts=2,
        max_duration=24.0,
        min_contact_score=110.0,
        min_score=40.0,
        max_group_span=14.0,
        pre_pad=2.0,
        post_pad=1.5,
    )
    candidates: list[dict] = []
    for window in relaxed:
        window_start = float(window["start"])
        window_end = float(window["end"])
        window_duration = max(0.1, window_end - window_start)
        for gap in gaps:
            gap_start = float(gap["start"])
            gap_end = float(gap["end"])
            overlap = max(
                0.0, min(window_end, gap_end) - max(window_start, gap_start)
            )
            if overlap < 0.6 * window_duration:
                continue
            start = max(gap_start, window_start)
            end = min(gap_end, window_end)
            if end - start < 3.0:
                continue
            if float(window.get("ball_pct", 0.0)) < min_ball_pct:
                continue
            candidate = dict(window)
            candidate.update(
                {
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "duration": round(end - start, 2),
                    "score": round(max(1.0, float(window["score"]) - 2.0), 1),
                    "source": "gap",
                    "gap": True,
                    "gap_start": round(gap_start, 2),
                }
            )
            candidates.append(candidate)
            break

    if not candidates:
        return []
    grouped: dict[float, list[dict]] = {}
    for candidate in candidates:
        grouped.setdefault(float(candidate["gap_start"]), []).append(candidate)
    for group in grouped.values():
        group.sort(
            key=lambda item: (float(item["score"]), float(item["duration"])),
            reverse=True,
        )

    selected: list[dict] = []
    for group in grouped.values():
        selected.extend(group[:max_per_gap])
    if len(selected) > max_total:
        firsts = [group[0] for group in grouped.values()]
        rest = sorted(
            [item for group in grouped.values() for item in group[1:]],
            key=lambda item: (float(item["score"]), float(item["duration"])),
            reverse=True,
        )
        selected = firsts + rest[: max(0, max_total - len(firsts))]

    selected.sort(key=lambda item: float(item["score"]), reverse=True)
    unique: list[dict] = []
    for candidate in selected:
        duplicate = False
        for existing in unique:
            overlap = max(
                0.0,
                min(float(candidate["end"]), float(existing["end"]))
                - max(float(candidate["start"]), float(existing["start"])),
            )
            if overlap > 1.5:
                duplicate = True
                break
        if not duplicate:
            unique.append(candidate)
    unique.sort(key=lambda item: float(item["start"]))
    return unique


def recovered_windows(
    rejections: list,
    records: list[dict],
    contact_times: list[float],
    duration: float,
    pre_roll: float,
    post_roll: float,
    max_total: int = 16,
    min_ball_pct: float = 0.04,
) -> list[dict]:
    windows: list[dict] = []
    for rejection in rejections:
        reason = rejection["reason"] or "other"
        reason = CLIP_REJECTION_CANONICAL.get(reason, reason)
        if reason != "bad_cut":
            continue
        detail = rejection["detail"] if "detail" in rejection.keys() else ""
        start = float(rejection["start"])
        end = float(rejection["end"])
        if detail in {"start_late", "both", ""}:
            start = max(0.0, start - pre_roll)
        if detail in {"end_early", "both", ""}:
            end = min(duration, end + post_roll)
        if end - start < 3.0 or end - start > 30.0:
            continue
        stats = window_stats(records, contact_times, start, end)
        if float(stats["ball_pct"]) < min_ball_pct:
            continue
        score = round(
            50.0
            + 20.0 * min(1.0, float(stats["ball_pct"]) / 0.5)
            + 20.0 * min(1.0, float(stats["contacts"]) / 5.0)
            + 10.0 * min(1.0, float(stats["max_speed"]) / 25.0),
            1,
        )
        windows.append(
            {
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": round(end - start, 2),
                "score": score,
                "max_speed": round(float(stats["max_speed"]), 1),
                "ball_pct": round(float(stats["ball_pct"]), 3),
                "contacts": int(stats["contacts"]),
                "crossings": 0,
                "min_y": None,
                "source": "recovered",
                "recovered": True,
                "detail": detail,
            }
        )
    windows.sort(key=lambda item: float(item["score"]), reverse=True)
    unique: list[dict] = []
    for candidate in windows:
        if len(unique) >= max_total:
            break
        duplicate = False
        for existing in unique:
            overlap = max(
                0.0,
                min(float(candidate["end"]), float(existing["end"]))
                - max(float(candidate["start"]), float(existing["start"])),
            )
            if overlap > 1.5:
                duplicate = True
                break
        if not duplicate:
            unique.append(candidate)
    unique.sort(key=lambda item: float(item["start"]))
    return unique


def overlapping_clips(
    clips: list,
    clip_id: int,
    start: float,
    end: float,
    min_coverage: float = 0.5,
    min_overlap: float = 2.0,
) -> list[dict]:
    duration = max(0.1, float(end) - float(start))
    result: list[dict] = []
    for other in clips:
        if int(other["id"]) == int(clip_id):
            continue
        other_start = float(other["start"])
        other_end = float(other["end"])
        overlap = max(0.0, min(float(end), other_end) - max(float(start), other_start))
        if overlap < 0.5:
            continue
        other_duration = max(0.1, other_end - other_start)
        coverage = overlap / min(duration, other_duration)
        if coverage < min_coverage and overlap < min_overlap:
            continue
        result.append(
            {
                "id": int(other["id"]),
                "start": round(other_start, 2),
                "end": round(other_end, 2),
                "duration": round(other_duration, 2),
                "status": other["status"],
                "starred": bool(other["starred"]),
                "score": float(other["score"] or 0.0),
                "overlap": round(overlap, 2),
                "coverage": round(coverage, 3),
            }
        )
    result.sort(key=lambda item: item["start"])
    return result


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
    parser.add_argument("--max-clips", type=int, default=100)
    parser.add_argument("--gap-clips", type=int, default=24)
    parser.add_argument("--ball", default="")
    parser.add_argument("--rallies", default="")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--no-activity", action="store_true")
    parser.add_argument("--activity", default="activity.json")
    parser.add_argument("--min-court-motion", type=float, default=4.0)
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

    from pipeline.activity import build_activity, filter_windows, load_activity

    activity = None
    if not args.no_activity:
        activity_path = job_dir / args.activity
        activity = load_activity(activity_path)
        if activity is None:
            print("atividade visual ausente; calculando agora...")
            try:
                build_activity(
                    args.match_id,
                    output=str(activity_path),
                    sample_fps=1.0,
                )
                activity = load_activity(activity_path)
            except Exception as exc:
                print(f"[aviso] filtro de quadra vazia indisponivel: {exc}")

    calibration = json.loads(match["calibration"]) if match["calibration"] else {}
    mode = calibration.get("mode", "full")
    min_y = None if mode == "full" else args.min_y
    net_x = {"full": 9.0, "center": 9.0, "near_attack": 12.0, "far_attack": 6.0}.get(
        mode, 9.0
    )
    print(f"modo={mode} net_x={net_x} min_y={min_y}")
    build_global_profile()
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

    contacts_path = job_dir / "contacts.json"
    contacts_payload = []
    if contacts_path.is_file():
        contacts_payload = json.loads(contacts_path.read_text(encoding="utf-8"))
    contact_times = [float(contact["t"]) for contact in contacts_payload]
    records_for_duration = [
        json.loads(line)
        for line in ball_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    duration = float(records_for_duration[-1]["t"]) if records_for_duration else 0.0
    existing_clips = list_clips(args.match_id)
    gaps = find_clip_gaps(existing_clips, duration)
    gap_candidates = (
        gap_windows(
            gaps,
            contacts_payload,
            records_for_duration,
            duration,
            max_total=args.gap_clips,
            min_ball_pct=max(0.06, min_ball_pct - 0.04),
        )
        if args.gap_clips > 0
        else []
    )
    rejection_rows = list_clip_rejections(args.match_id)
    recovered = recovered_windows(
        rejection_rows,
        records_for_duration,
        contact_times,
        duration,
        pre_roll=float(trim_profile.get("pre_roll", 1.0)),
        post_roll=float(trim_profile.get("post_roll", 1.8)),
        min_ball_pct=max(0.04, min_ball_pct * 0.5),
    )
    print(
        f"lacunas_sem_clipes={len(gaps)} candidatos_lacuna={len(gap_candidates)} "
        f"recuperados={len(recovered)}"
    )
    contact_candidates = (
        contact_windows(contacts_payload, records_for_duration, duration)
        if contacts_payload
        else []
    )
    use_audio = (
        not args.no_audio
        and (match["whistle_mode"] if "whistle_mode" in match.keys() else "with")
        != "without"
    )
    print(
        f"apito={'sim' if use_audio else 'nao'} "
        f"janelas_contato={len(contact_candidates)}"
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
    if use_audio and rallies_path.is_file():
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

    windows: list[dict] = sorted(audio_windows, key=lambda item: item["start"])

    def add_complement(candidate: dict, max_overlap: float = 1.5) -> None:
        for existing in windows:
            overlap = max(
                0.0,
                min(candidate["end"], existing["end"])
                - max(candidate["start"], existing["start"]),
            )
            if overlap > max_overlap:
                return
        windows.append(candidate)

    for candidate in sorted(contact_candidates, key=lambda item: item["start"]):
        if float(candidate.get("ball_pct", 0.0)) < min_ball_pct:
            continue
        add_complement(candidate)

    for window in speed_windows:
        duration_window = float(window["end"]) - float(window["start"])
        if duration_window > 20.0 or float(window["score"]) < 55.0:
            continue
        window["source"] = "speed"
        add_complement(window)

    for candidate in gap_candidates:
        add_complement(candidate)

    if not windows:
        for window in speed_windows:
            window["source"] = "speed"
        windows = speed_windows
    windows.sort(key=lambda item: item["start"])

    rejections = rejection_rows
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

    if activity:
        windows, activity_dropped = filter_windows(
            windows,
            activity,
            min_mean=args.min_court_motion,
        )
        print(f"ignorados por quadra vazia/parada: {activity_dropped}")

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

    for candidate in recovered:
        duplicate = False
        for saved in saved_clips:
            overlap = max(
                0.0,
                min(candidate["end"], saved["end"])
                - max(candidate["start"], saved["start"]),
            )
            saved_duration = max(0.1, saved["end"] - saved["start"])
            if overlap / min(candidate["duration"], saved_duration) > 0.5:
                duplicate = True
                break
        if not duplicate:
            add_complement(candidate)

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

    protected = [
        window
        for window in windows
        if window.get("gap") or window.get("recovered")
    ]
    regular = [
        window
        for window in windows
        if not (window.get("gap") or window.get("recovered"))
    ]
    if len(regular) > args.max_clips:
        regular.sort(key=lambda item: float(item["score"]), reverse=True)
        print(
            f"limite de {args.max_clips} candidatos comuns aplicado "
            f"({len(regular)} -> {args.max_clips})"
        )
        regular = regular[: args.max_clips]
    windows = sorted(
        protected + regular, key=lambda item: float(item["start"])
    )
    gap_total = sum(1 for window in windows if window.get("gap"))
    recovered_total = sum(1 for window in windows if window.get("recovered"))
    print(
        f"candidatos: {len(windows)} (audio={len(audio_windows)}, "
        f"lacuna={gap_total}, recuperados={recovered_total})"
    )
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

    clips_dir = clip_dir_for_match(args.match_id)
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
                "activity_mean",
                "activity_max",
                "activity_active_pct",
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
