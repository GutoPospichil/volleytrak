from __future__ import annotations

import math


def format_time(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def build_timeline(
    clips: list,
    duration: float,
    bin_seconds: int = 60,
    min_gap_seconds: int = 60,
) -> dict:
    total = max(1, int(math.ceil(duration)))
    covered_new = bytearray(total)
    covered_saved = bytearray(total)
    covered_any = bytearray(total)

    for clip in clips:
        start = max(0, int(math.floor(float(clip["start"]))))
        end = min(total, int(math.ceil(float(clip["end"]))))
        target = covered_saved if clip["status"] == "saved" else covered_new
        for index in range(start, end):
            covered_any[index] = 1
            target[index] = 1

    bins = []
    count = max(1, int(math.ceil(total / bin_seconds)))
    for index in range(count):
        start = index * bin_seconds
        end = min(total, start + bin_seconds)
        size = max(1, end - start)
        new_count = sum(covered_new[start:end])
        saved_count = sum(covered_saved[start:end])
        any_count = sum(covered_any[start:end])
        coverage = round(100.0 * any_count / size, 1)
        level = 0
        if coverage > 0:
            level = 1
        if coverage > 25:
            level = 2
        if coverage > 50:
            level = 3
        if coverage > 75:
            level = 4
        bins.append(
            {
                "start": float(start),
                "end": float(end),
                "label": format_time(start),
                "coverage": coverage,
                "level": level,
                "new": new_count,
                "saved": saved_count,
                "has_saved": saved_count > 0,
                "minute": start // 60,
            }
        )

    gaps = []
    index = 0
    while index < total:
        if covered_any[index]:
            index += 1
            continue
        start = index
        while index < total and not covered_any[index]:
            index += 1
        gap_duration = index - start
        if gap_duration >= min_gap_seconds:
            gaps.append(
                {
                    "start": float(start),
                    "end": float(index),
                    "duration": float(gap_duration),
                    "start_label": format_time(start),
                    "end_label": format_time(index),
                    "duration_label": format_time(gap_duration),
                }
            )

    covered_total = sum(covered_any)
    return {
        "bins": bins,
        "gaps": gaps,
        "coverage_pct": round(100.0 * covered_total / total, 1),
        "gap_total": sum(gap["duration"] for gap in gaps),
        "duration": duration,
    }
