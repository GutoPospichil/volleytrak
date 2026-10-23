from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from app.config import JOB_DIR
from app.db import get_match


def load_json(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


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
    ball = max(candidates, key=lambda item: item.get("score", 0.0))
    return [float(ball["court"][0]), float(ball["court"][1])]


def track_stats(records: list[dict], start: float, end: float) -> dict:
    window = [record for record in records if start <= record["t"] <= end]
    if not window:
        return {"ball_pct": 0.0, "max_speed": 0.0, "samples": 0}
    samples = []
    for record in window:
        court = best_court(record)
        if court is not None:
            samples.append((float(record["t"]), court))
    max_speed = 0.0
    for (t0, p0), (t1, p1) in zip(samples, samples[1:]):
        dt = t1 - t0
        if dt <= 0 or dt > 0.25:
            continue
        speed = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / dt
        if speed <= 35.0:
            max_speed = max(max_speed, speed)
    return {
        "ball_pct": len(samples) / len(window),
        "max_speed": max_speed,
        "samples": len(samples),
        "window": len(window),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", type=int, required=True)
    parser.add_argument("--whistles", default="whistles.json")
    parser.add_argument("--ball", default="")
    parser.add_argument("--contacts", default="contacts.json")
    parser.add_argument("--output", default="rallies_audio.json")
    parser.add_argument("--min-duration", type=float, default=2.0)
    parser.add_argument("--max-duration", type=float, default=30.0)
    parser.add_argument("--min-ball-pct", type=float, default=0.10)
    parser.add_argument("--min-speed", type=float, default=5.0)
    parser.add_argument("--pair-mode", choices=["disjoint", "adjacent"], default="disjoint")
    args = parser.parse_args()

    match = get_match(args.match_id)
    if match is None:
        print("partida não encontrada")
        return 1
    job_dir = JOB_DIR / f"match-{args.match_id}"
    whistles = load_json(job_dir / args.whistles)
    if not whistles:
        print("nenhum apito encontrado; rode pipeline.audio primeiro")
        return 1
    ball_path = job_dir / (args.ball or "ball_vballnet.jsonl")
    if not args.ball and not ball_path.is_file():
        ball_path = job_dir / "ball_dfine.jsonl"
    if not ball_path.is_file():
        print("track de bola não encontrada")
        return 1
    records = [
        json.loads(line)
        for line in ball_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    contacts = load_json(job_dir / args.contacts)
    contacts_times = [contact["t"] for contact in contacts]
    duration = records[-1]["t"] if records else 0.0

    rallies = []
    if args.pair_mode == "disjoint":
        pairs = zip(whistles[0::2], whistles[1::2])
    else:
        pairs = zip(whistles, whistles[1:])
    for first, second in pairs:
        t0 = float(first["t"])
        t1 = float(second["t"])
        if t1 - t0 < args.min_duration or t1 - t0 > args.max_duration:
            continue
        stats = track_stats(records, t0, t1)
        if stats["ball_pct"] < args.min_ball_pct or stats["max_speed"] < args.min_speed:
            continue
        start = max(0.0, t0 - 1.0)
        end = min(duration, t1 + 1.5)
        if end - start < 3.0:
            continue
        contact_count = sum(1 for t in contacts_times if start <= t <= end)
        ball_score = min(1.0, stats["ball_pct"] / 0.4)
        speed_score = min(1.0, stats["max_speed"] / 25.0)
        contact_score = min(1.0, contact_count / 4.0)
        confidence = min(1.0, (float(first["score"]) + float(second["score"])) / 0.12)
        score = round(
            100.0
            * (
                0.35 * ball_score
                + 0.25 * speed_score
                + 0.15 * contact_score
                + 0.10 * confidence
            )
            + 25.0,
            1,
        )
        rallies.append(
            {
                "start": round(start, 1),
                "end": round(end, 1),
                "duration": round(end - start, 1),
                "whistle_start": round(t0, 2),
                "whistle_end": round(t1, 2),
                "ball_pct": round(stats["ball_pct"], 3),
                "max_speed": round(stats["max_speed"], 1),
                "contacts": contact_count,
                "score": score,
            }
        )

    rallies.sort(key=lambda item: item["start"])
    output_path = job_dir / args.output
    output_path.write_text(json.dumps(rallies, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"rallies por apito: {len(rallies)}")
    for rally in rallies:
        print(
            f"  {rally['start']:7.1f}-{rally['end']:7.1f}s "
            f"ball={rally['ball_pct']:.2f} speed={rally['max_speed']:5.1f} "
            f"contacts={rally['contacts']} score={rally['score']:.1f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
