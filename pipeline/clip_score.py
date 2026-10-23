from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from app.config import JOB_DIR
from app.db import get_match, list_clips, update_clip_features, update_clip_saved_score


def load_json(path: Path, fallback):
    if not path.is_file():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path, fallback):
    if not path.is_file():
        return fallback
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def best_court(record: dict) -> list[float] | None:
    candidates = [
        ball
        for ball in record.get("balls", [])
        if ball.get("court")
        and -2.5 <= ball["court"][0] <= 20.5
        and -2.5 <= ball["court"][1] <= 11.5
        and ball.get("score", 0.0) >= 0.3
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.get("score", 0.0))["court"]


def stats_for_window(records: list[dict], start: float, end: float) -> dict:
    samples = []
    for record in records:
        if not (start <= record["t"] <= end):
            continue
        court = best_court(record)
        if court is not None:
            samples.append((float(record["t"]), [float(court[0]), float(court[1])]))
    max_speed = 0.0
    for (t0, p0), (t1, p1) in zip(samples, samples[1:]):
        gap = t1 - t0
        if gap <= 0 or gap > 0.25:
            continue
        speed = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / gap
        if 0 < speed <= 35.0:
            max_speed = max(max_speed, speed)
    return {
        "ball_pct": len(samples) / max(1, sum(1 for record in records if start <= record["t"] <= end)),
        "max_speed": max_speed,
        "samples": len(samples),
    }


def score_clip(clip, records: list[dict], contacts: list[float], rallies: list[dict]) -> tuple[float, dict]:
    duration = float(clip["duration"])
    features = {}
    if clip["features"]:
        try:
            features = json.loads(clip["features"])
        except (TypeError, json.JSONDecodeError):
            features = {}
    stats = stats_for_window(records, float(clip["start"]), float(clip["end"]))
    features.setdefault("ball_pct", round(stats["ball_pct"], 4))
    features.setdefault("max_speed", round(stats["max_speed"], 2))
    features.setdefault("contacts", sum(1 for t in contacts if float(clip["start"]) <= t <= float(clip["end"])))
    source = clip["source"] or "speed"
    starred = bool(clip["starred"])
    for rally in rallies:
        if rally["start"] <= clip["start"] + 0.5 and rally["end"] >= clip["end"] - 0.5:
            source = "audio"
            features.setdefault("whistle_start", rally.get("whistle_start"))
            features.setdefault("whistle_end", rally.get("whistle_end"))
            break

    base = float(clip["score"] or 0.0)
    ball = min(1.0, float(features.get("ball_pct") or 0.0) / 0.45)
    contact = min(1.0, float(features.get("contacts") or 0.0) / 6.0)
    speed = min(1.0, float(features.get("max_speed") or 0.0) / 25.0)
    duration_score = max(0.0, 1.0 - abs(duration - 12.0) / 14.0)
    source_bonus = 4.0 if source == "audio" else 0.0
    quality = (
        0.40 * base
        + 0.25 * ball * 100.0
        + 0.15 * contact * 100.0
        + 0.10 * speed * 100.0
        + 0.10 * duration_score * 100.0
        + source_bonus
        + (8.0 if starred else 0.0)
    )
    features.update(
        {
            "source": source,
            "score": round(min(100.0, quality), 1),
            "duration": round(duration, 2),
            "base_score": round(base, 1),
            "starred": starred,
        }
    )
    return round(min(100.0, quality), 1), features


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", type=int, required=True)
    args = parser.parse_args()
    match = get_match(args.match_id)
    if match is None:
        print("partida não encontrada")
        return 1
    job_dir = JOB_DIR / f"match-{args.match_id}"
    ball_path = job_dir / "ball_vballnet.jsonl"
    if not ball_path.is_file():
        ball_path = job_dir / "ball_dfine.jsonl"
    records = load_jsonl(ball_path, [])
    contacts = [float(item["t"]) for item in load_json(job_dir / "contacts.json", [])]
    rallies = load_json(job_dir / "rallies_audio.json", [])
    clips = list_clips(args.match_id, "saved")
    if not clips:
        print("nenhum clipe salvo")
        return 0
    if not records:
        print("track de bola não encontrada; usando score original")
    for clip in clips:
        quality, features = score_clip(clip, records, contacts, rallies)
        update_clip_saved_score(clip["id"], quality)
        update_clip_features(clip["id"], features)
        print(
            f"{clip['id']} {clip['start']:.1f}-{clip['end']:.1f}s "
            f"nota={quality:.1f} ball={features.get('ball_pct', 0):.2f} "
            f"contatos={features.get('contacts', 0)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
