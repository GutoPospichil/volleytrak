from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np


def select_balls(record: dict) -> list[dict]:
    return [
        ball
        for ball in record.get("balls", [])
        if ball.get("court")
        and -1.0 <= ball["court"][0] <= 19.0
        and -1.0 <= ball["court"][1] <= 10.0
        and ball.get("score", 0.0) >= 0.3
    ]


def speed_series(
    records: list[dict], net_x: float = 9.0
) -> tuple[list[float], list[tuple[float, float]]]:
    speeds = []
    crossings = []
    for index, record in enumerate(records):
        best = 0.0
        balls = select_balls(record)
        if balls:
            for previous_index in range(index - 1, max(-1, index - 3), -1):
                previous = records[previous_index]
                dt = record["t"] - previous["t"]
                if dt <= 0 or dt > 0.45:
                    continue
                previous_balls = select_balls(previous)
                if not previous_balls:
                    continue
                for ball in balls:
                    for old in previous_balls:
                        distance = math.hypot(
                            ball["court"][0] - old["court"][0],
                            ball["court"][1] - old["court"][1],
                        )
                        speed = distance / dt
                        if 0 < speed <= 32 and speed > best:
                            best = speed
                            if (
                                (old["court"][0] - net_x) * (ball["court"][0] - net_x) < 0
                                and distance > 1.5
                            ):
                                crossings.append((record["t"], speed))
                if best > 0:
                    break
        speeds.append(best)

    deduped = []
    for crossing in sorted(crossings):
        if deduped and crossing[0] - deduped[-1][0] < 0.4:
            continue
        deduped.append(crossing)
    return speeds, deduped


def windows_from_ball(
    path: Path,
    threshold: float = 3.0,
    min_y: float | None = 300.0,
    min_score: float = 50.0,
    max_clips: int = 40,
    net_x: float = 9.0,
) -> list[dict]:
    records = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            records.append(json.loads(line))
    if not records:
        return []

    duration = records[-1]["t"]
    speeds, crossings = speed_series(records, net_x=net_x)
    values = np.array(speeds, dtype=float)
    smoothed = np.convolve(values, np.ones(3) / 3, mode="same")
    times = np.array([record["t"] for record in records])

    active_times = times[smoothed >= threshold]
    groups = []
    for t in active_times:
        if groups and t - groups[-1][-1] <= 1.6:
            groups[-1].append(t)
        else:
            groups.append([t])

    candidates = []
    for group in groups:
        start = max(0.0, group[0] - 2.5)
        end = min(duration, group[-1] + 1.5)
        if end - start < 3.0 or len(group) < 5:
            continue
        candidates.append((start, end, len(group)))

    merged = []
    for candidate in candidates:
        if merged and candidate[0] - merged[-1][1] < 2.0:
            merged[-1] = (
                merged[-1][0],
                candidate[1],
                merged[-1][2] + candidate[2],
            )
        else:
            merged.append(candidate)

    windows = []
    for start, end, active_samples in merged:
        window_balls = [
            ball
            for record in records
            if start <= record["t"] <= end
            for ball in select_balls(record)
        ]
        if not window_balls:
            continue
        heights = [(ball["box"][1] + ball["box"][3]) / 2 for ball in window_balls]
        highest = min(heights)
        if min_y is not None and highest > min_y:
            continue
        window_crossings = sum(1 for t, _ in crossings if start <= t <= end)
        if min_y is None and window_crossings < 1:
            continue
        max_speed = max(
            (speed for t, speed in zip(times, speeds) if start <= t <= end),
            default=0.0,
        )
        speed_score = min(1.0, max_speed / 25.0)
        crossing_score = min(1.0, window_crossings / 3.0)
        if min_y is None:
            depths = [ball["court"][0] for ball in window_balls]
            depth_score = min(1.0, (max(depths) - min(depths)) / 14.0)
            active_score = min(1.0, active_samples / max(1.0, (end - start) * 3.0))
            score = round(
                100.0
                * (
                    0.50 * speed_score
                    + 0.25 * crossing_score
                    + 0.15 * depth_score
                    + 0.10 * active_score
                ),
                1,
            )
        else:
            height_score = min(1.0, max(0.0, (350.0 - highest) / 120.0))
            score = round(
                100.0
                * (0.45 * speed_score + 0.35 * height_score + 0.20 * crossing_score),
                1,
            )
        if score < min_score:
            continue
        windows.append(
            {
                "start": round(start, 1),
                "end": round(end, 1),
                "duration": round(end - start, 1),
                "active_samples": active_samples,
                "max_speed": round(max_speed, 1),
                "min_y": round(highest, 1),
                "crossings": window_crossings,
                "score": score,
            }
        )

    windows.sort(key=lambda item: item["start"])
    return windows[:max_clips]
