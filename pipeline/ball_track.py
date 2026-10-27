from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from app.config import JOB_DIR
from app.db import get_match


COURT_X = (-2.5, 20.5)
COURT_Y = (-2.5, 11.5)


def load_records(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def candidates(record: dict) -> list[dict]:
    result = []
    for ball in record.get("balls") or []:
        court = ball.get("court")
        if not court or len(court) < 2:
            continue
        x, y = float(court[0]), float(court[1])
        if not (COURT_X[0] <= x <= COURT_X[1] and COURT_Y[0] <= y <= COURT_Y[1]):
            continue
        score = float(ball.get("score") or 0.0)
        if score < 0.2:
            continue
        result.append(
            {
                "center": ball.get("center"),
                "box": ball.get("box"),
                "score": score,
                "court": [x, y],
            }
        )
    return result


def initial_state(court: list[float]) -> np.ndarray:
    return np.array([court[0], court[1], 0.0, 0.0], dtype=float)


def predict(state: np.ndarray, cov: np.ndarray, dt: float, q: float) -> tuple[np.ndarray, np.ndarray]:
    transition = np.array(
        [
            [1.0, 0.0, dt, 0.0],
            [0.0, 1.0, 0.0, dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    q_matrix = q * np.array(
        [
            [dt**4 / 4.0, 0.0, dt**3 / 2.0, 0.0],
            [0.0, dt**4 / 4.0, 0.0, dt**3 / 2.0],
            [dt**3 / 2.0, 0.0, dt**2, 0.0],
            [0.0, dt**3 / 2.0, 0.0, dt**2],
        ]
    )
    return transition @ state, transition @ cov @ transition.T + q_matrix


def update(
    state: np.ndarray,
    cov: np.ndarray,
    measurement: np.ndarray,
    r: float,
) -> tuple[np.ndarray, np.ndarray]:
    observation = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])
    innovation_cov = observation @ cov @ observation.T + r * np.eye(2)
    gain = cov @ observation.T @ np.linalg.inv(innovation_cov)
    state = state + gain @ (measurement - observation @ state)
    cov = (np.eye(4) - gain @ observation) @ cov
    return state, cov


def inside_court(court: list[float]) -> bool:
    return COURT_X[0] <= court[0] <= COURT_X[1] and COURT_Y[0] <= court[1] <= COURT_Y[1]


def track_ball(
    match_id: int,
    input_path: Path,
    output_path: Path,
    max_gap: float = 0.30,
    gate: float = 2.6,
    max_speed: float = 42.0,
    process_noise: float = 0.9,
    measurement_noise: float = 0.8,
    min_hits: int = 3,
    min_track_duration: float = 0.10,
) -> dict:
    records = load_records(input_path)
    started = time.time()
    track_state = None
    track_cov = None
    last_time = None
    last_hit_time = None
    last_score = 0.0
    hits = 0
    confirmed = False
    pending: list[tuple[int, float, dict]] = []
    tracks_started = 0
    tracks_confirmed = 0
    interpolated = 0
    frames_with_ball = 0
    output = [
        {"frame": record.get("frame"), "t": record.get("t"), "balls": []}
        for record in records
    ]

    def emit(index: int, chosen: dict, is_interpolated: bool) -> None:
        nonlocal frames_with_ball, interpolated
        output[index] = {
            "frame": records[index].get("frame"),
            "t": records[index].get("t"),
            "balls": [
                {
                    "center": chosen.get("center"),
                    "box": chosen.get("box"),
                    "score": chosen.get("score"),
                    "court": chosen.get("court"),
                    "interpolated": bool(is_interpolated),
                }
            ],
        }
        frames_with_ball += 1
        if is_interpolated:
            interpolated += 1

    def start_track(index: int, t: float, ball: dict) -> None:
        nonlocal track_state, track_cov, last_time, last_hit_time, last_score
        nonlocal hits, confirmed, pending, tracks_started
        track_state = initial_state(ball["court"])
        track_cov = np.eye(4) * 4.0
        last_time = t
        last_hit_time = t
        last_score = ball["score"]
        hits = 1
        confirmed = False
        pending = [(index, t, ball)]
        tracks_started += 1

    for index, record in enumerate(records):
        t = float(record.get("t") or 0.0)
        found = candidates(record)
        chosen = None
        is_interpolated = False

        if track_state is not None:
            if t - last_hit_time > max_gap:
                track_state = None
                track_cov = None
                pending = []
                confirmed = False

        if track_state is not None and last_hit_time is not None:
            dt = max(1e-3, min(max_gap, t - last_time))
            track_state, track_cov = predict(
                track_state, track_cov, dt, process_noise
            )
            predicted = track_state[:2]
            best = None
            best_cost = None
            for candidate in found:
                distance = float(
                    np.hypot(
                        candidate["court"][0] - predicted[0],
                        candidate["court"][1] - predicted[1],
                    )
                )
                if distance > gate:
                    continue
                cost = distance - 0.45 * candidate["score"]
                if best_cost is None or cost < best_cost:
                    best = candidate
                    best_cost = cost
            if best is not None:
                track_state, track_cov = update(
                    track_state,
                    track_cov,
                    np.array(best["court"], dtype=float),
                    measurement_noise,
                )
                chosen = best
                last_score = best["score"]
                last_hit_time = t
                hits += 1
            else:
                velocity = float(np.hypot(track_state[2], track_state[3]))
                if velocity <= max_speed and inside_court(predicted.tolist()):
                    chosen = {
                        "center": None,
                        "box": None,
                        "score": round(max(0.3, min(0.5, last_score * 0.75)), 4),
                        "court": [
                            round(float(predicted[0]), 3),
                            round(float(predicted[1]), 3),
                        ],
                        "interpolated": True,
                    }
                    is_interpolated = True

        if track_state is None:
            if found:
                best = max(found, key=lambda item: item["score"])
                if best["score"] >= 0.3:
                    start_track(index, t, best)
                    chosen = best
            if chosen is None:
                last_time = t
                continue

        if not confirmed:
            pending.append((index, t, chosen))
            if chosen.get("interpolated"):
                # Não confirma uma trilha apenas com pontos inventados.
                track_state = None
                track_cov = None
                pending = []
                last_time = t
                continue
            if hits >= min_hits and t - pending[0][1] >= min_track_duration:
                confirmed = True
                tracks_confirmed += 1
                for pending_index, _, pending_ball in pending:
                    emit(
                        pending_index,
                        pending_ball,
                        bool(pending_ball.get("interpolated")),
                    )
                pending = []
            last_time = t
            continue

        if chosen is None:
            last_time = t
            continue
        emit(index, chosen, is_interpolated)
        last_time = t

    output_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in output) + "\n",
        encoding="utf-8",
    )
    payload = {
        "match_id": match_id,
        "input": input_path.name,
        "output": output_path.name,
        "frames": len(records),
        "frames_with_ball": frames_with_ball,
        "ball_frame_pct": round(frames_with_ball / max(1, len(records)), 4),
        "interpolated": interpolated,
        "tracks_started": tracks_started,
        "tracks_confirmed": tracks_confirmed,
        "max_gap": max_gap,
        "gate": gate,
        "elapsed_s": round(time.time() - started, 2),
    }
    (output_path.parent / "ball_track.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"tracking: {frames_with_ball}/{len(records)} frames com bola "
        f"({payload['ball_frame_pct'] * 100:.1f}%), {interpolated} interpolados, "
        f"{tracks_confirmed}/{tracks_started} trilhas confirmadas, "
        f"{payload['elapsed_s']}s"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", type=int, required=True)
    parser.add_argument("--input", default="ball_vballnet.jsonl")
    parser.add_argument("--output", default="ball_track.jsonl")
    parser.add_argument("--max-gap", type=float, default=0.30)
    parser.add_argument("--gate", type=float, default=2.6)
    parser.add_argument("--max-speed", type=float, default=42.0)
    args = parser.parse_args()

    match = get_match(args.match_id)
    if match is None:
        print("partida não encontrada")
        return 1
    job_dir = JOB_DIR / f"match-{args.match_id}"
    input_path = job_dir / args.input
    if not input_path.is_file():
        print(f"bola não encontrada: {input_path}")
        return 1
    track_ball(
        args.match_id,
        input_path,
        job_dir / args.output,
        max_gap=args.max_gap,
        gate=args.gate,
        max_speed=args.max_speed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
