from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks

from app.config import JOB_DIR
from app.db import get_match


def best_ball(record: dict) -> dict | None:
    candidates = [
        ball
        for ball in record.get("balls", [])
        if ball.get("court")
        and -1.0 <= ball["court"][0] <= 19.0
        and -1.0 <= ball["court"][1] <= 10.0
        and (ball.get("interpolated") or ball.get("score", 0.0) >= 0.3)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda ball: ball.get("score", 0.0))


def detect_contacts(
    records: list[dict], max_gap: float = 0.25, max_speed: float = 45.0
) -> list[dict]:
    segments: list[list[dict]] = []
    current: list[dict] = []
    previous: dict | None = None
    for record in records:
        ball = best_ball(record)
        if ball is None or ball.get("interpolated"):
            if current:
                segments.append(current)
                current = []
            previous = None
            continue
        sample = {
            "t": float(record["t"]),
            "x": float(ball["court"][0]),
            "y": float(ball["court"][1]),
            "score": float(ball.get("score", 0.0)),
        }
        if current and sample["t"] - current[-1]["t"] > max_gap:
            segments.append(current)
            current = []
            previous = None
        if previous is not None:
            gap = sample["t"] - previous["t"]
            jump = math.hypot(sample["x"] - previous["x"], sample["y"] - previous["y"])
            if gap > 1e-6 and jump / gap > max_speed:
                # heatmap trocou de objeto/pessoa; descarta o salto
                if current:
                    segments.append(current)
                    current = []
                previous = None
                continue
        current.append(sample)
        previous = sample
    if current:
        segments.append(current)

    contacts: list[dict] = []
    for segment in segments:
        if len(segment) < 4:
            continue
        times = np.array([item["t"] for item in segment])
        xs = np.array([item["x"] for item in segment])
        ys = np.array([item["y"] for item in segment])
        dt = np.diff(times)
        dt = np.where(dt <= 1e-6, 1e-6, dt)
        vx = np.diff(xs) / dt
        vy = np.diff(ys) / dt
        speed = np.hypot(vx, vy)
        if len(speed) < 3:
            continue
        # angle between consecutive velocity vectors, in degrees
        dot = vx[:-1] * vx[1:] + vy[:-1] * vy[1:]
        norm = (np.hypot(vx[:-1], vy[:-1]) * np.hypot(vx[1:], vy[1:])) + 1e-9
        turn = np.degrees(np.arccos(np.clip(dot / norm, -1.0, 1.0)))
        accel = np.abs(np.diff(speed)) / ((dt[:-1] + dt[1:]) / 2.0)
        turn = np.where(speed[:-1] > 2.0, turn, 0.0)
        accel = np.where(speed[:-1] > 2.0, accel, 0.0)
        score_signal = turn + np.clip(accel, 0.0, 80.0) * 0.8
        if not len(score_signal):
            continue
        prominence = max(8.0, float(np.percentile(score_signal, 80)) * 0.25)
        peaks, properties = find_peaks(
            score_signal,
            distance=max(1, int(round(0.22 / max(float(np.mean(dt)), 0.01)))),
            prominence=prominence,
        )
        for peak in peaks:
            index = min(len(segment) - 2, int(peak) + 1)
            if score_signal[peak] < 18.0:
                continue
            contacts.append(
                {
                    "t": round(float(times[index]), 3),
                    "court": [round(float(xs[index]), 2), round(float(ys[index]), 2)],
                    "speed": round(float(speed[min(peak, len(speed) - 1)]), 2),
                    "turn_deg": round(float(turn[peak]), 1),
                    "accel": round(float(accel[peak]), 1),
                    "score": round(float(score_signal[peak]), 1),
                }
            )

    contacts.sort(key=lambda item: item["t"])
    deduped: list[dict] = []
    for contact in contacts:
        if deduped and contact["t"] - deduped[-1]["t"] < 0.35:
            if contact["score"] > deduped[-1]["score"]:
                deduped[-1] = contact
            continue
        deduped.append(contact)
    return deduped


def validate_contacts(
    contacts: list[dict], reference_records: list[dict], max_gap: float = 0.4
) -> list[dict]:
    reference = []
    for record in reference_records:
        ball = best_ball(record)
        if ball is not None:
            reference.append((float(record["t"]), ball["court"]))
    if not reference:
        return contacts
    reference.sort(key=lambda item: item[0])
    times = np.array([item[0] for item in reference])
    kept = []
    for contact in contacts:
        index = int(np.searchsorted(times, contact["t"]))
        candidates = []
        for neighbor in (index - 1, index):
            if 0 <= neighbor < len(reference):
                candidates.append(reference[neighbor])
        if not candidates:
            continue
        best = min(candidates, key=lambda item: abs(item[0] - contact["t"]))
        if abs(best[0] - contact["t"]) > max_gap:
            continue
        distance = math.hypot(
            best[1][0] - contact["court"][0], best[1][1] - contact["court"][1]
        )
        if distance <= 2.2:
            kept.append(contact)
    return kept


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", type=int, required=True)
    parser.add_argument("--input", default="ball_track.jsonl")
    parser.add_argument("--output", default="contacts.json")
    parser.add_argument("--validate", default="ball_dfine.jsonl")
    args = parser.parse_args()

    match = get_match(args.match_id)
    if match is None:
        print("partida não encontrada")
        return 1
    job_dir = JOB_DIR / f"match-{args.match_id}"
    input_path = job_dir / args.input
    if not input_path.is_file():
        input_path = job_dir / "ball_vballnet.jsonl"
    if not input_path.is_file():
        print(f"track não encontrada: {input_path}")
        return 1
    records = [
        json.loads(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    contacts = detect_contacts(records)
    if args.validate:
        reference_path = job_dir / args.validate
        if reference_path.is_file():
            reference_records = [
                json.loads(line)
                for line in reference_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            before = len(contacts)
            contacts = validate_contacts(contacts, reference_records)
            print(f"validação D-FINE: {before} -> {len(contacts)} contatos")
    output_path = job_dir / args.output
    output_path.write_text(json.dumps(contacts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"contatos: {len(contacts)} em {len(records)} frames")
    for contact in contacts[:20]:
        print(
            f"  {contact['t']:.2f}s court={contact['court']} "
            f"speed={contact['speed']} turn={contact['turn_deg']} score={contact['score']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
