from __future__ import annotations


def derive_touches(
    candidates: list[dict],
    per_track_gap: float = 0.8,
    global_gap: float = 0.2,
) -> list[dict]:
    ordered = sorted(candidates, key=lambda item: item["t"])
    last_track: dict[int, float] = {}
    last_global: float | None = None
    touches: list[dict] = []

    for candidate in ordered:
        track_id = candidate.get("track_id")
        if track_id is None:
            continue
        if last_global is not None and candidate["t"] - last_global < global_gap:
            continue
        previous = last_track.get(track_id)
        if previous is not None and candidate["t"] - previous < per_track_gap:
            continue
        touches.append(candidate)
        last_track[track_id] = candidate["t"]
        last_global = candidate["t"]

    return touches
