from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

from app.config import JOB_DIR, MODEL_DIR
from app.db import get_match
from pipeline.calibration import homography_from_points, project_point
from pipeline.dfine import detect, load_detector


def in_play_area(point: list[float] | None, margin: float = 2.5) -> bool:
    if point is None:
        return False
    return -margin <= point[0] <= 18.0 + margin and -margin <= point[1] <= 9.0 + margin


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", type=int, required=True)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--tile", type=int, default=864)
    parser.add_argument("--threshold", type=float, default=0.3)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, default=None)
    parser.add_argument(
        "--model",
        default=str(MODEL_DIR / "volleyball-dfine"),
    )
    args = parser.parse_args()

    match = get_match(args.match_id)
    if match is None:
        print(f"partida {args.match_id} não encontrada")
        return 1
    video_path = Path(match["video_path"])
    if not video_path.is_file():
        print("vídeo não encontrado")
        return 1

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, processor = load_detector(args.model, device)
    print(f"model loaded device={device}", flush=True)

    calibration = json.loads(match["calibration"]) if match["calibration"] else None
    calibration_points = calibration.get("points") if calibration else None
    calibration_mode = calibration.get("mode", "full") if calibration else "full"

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        print("não foi possível abrir o vídeo")
        return 1
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, int(round(fps / max(args.fps, 0.5))))
    if args.start > 0:
        capture.set(cv2.CAP_PROP_POS_MSEC, args.start * 1000)
    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    matrix = None
    if calibration_points:
        matrix = homography_from_points(
            calibration_points, (frame_width, frame_height), calibration_mode
        )

    job_dir = JOB_DIR / f"match-{args.match_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    detections_path = job_dir / "ball_dfine.jsonl"
    track_path = job_dir / "ball_track.csv"
    meta_path = job_dir / "ball_pass.json"

    track = None
    velocity = (0.0, 0.0)
    last_seen = None
    frame_index = int(args.start * fps)
    sampled = 0
    track_hits = 0
    ball_frames = 0
    started = time.time()

    with detections_path.open("w", encoding="utf-8") as detections_file, track_path.open(
        "w", encoding="utf-8"
    ) as track_file:
        track_file.write("t,x_img,y_img,x_court,y_court,score,detected\n")
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            t = frame_index / fps
            if args.end is not None and t > args.end:
                break
            if t < args.start or frame_index % step != 0:
                frame_index += 1
                continue

            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            raw_balls = detect(
                model,
                processor,
                image,
                device,
                tile=args.tile,
                threshold=args.threshold,
                labels={"ball"},
            )

            balls = []
            for detection in raw_balls:
                x1, y1, x2, y2 = detection["box"]
                center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
                court = project_point(matrix, center)
                balls.append(
                    {
                        "box": detection["box"],
                        "score": detection["score"],
                        "center": [round(center[0], 1), round(center[1], 1)],
                        "court": [round(value, 2) for value in court] if court else None,
                        "in_play": in_play_area(court) if matrix is not None else True,
                    }
                )

            chosen = None
            if track is not None and last_seen is not None and t - last_seen <= 2.0:
                prediction = (track[0] + velocity[0], track[1] + velocity[1])
                best_score = -1e9
                for ball in balls:
                    if not ball["in_play"]:
                        continue
                    distance = float(
                        np.hypot(
                            ball["center"][0] - prediction[0],
                            ball["center"][1] - prediction[1],
                        )
                    )
                    if distance > 300:
                        continue
                    score = ball["score"] * 80.0 - distance
                    if score > best_score:
                        best_score = score
                        chosen = ball

            if chosen is None:
                pool = [ball for ball in balls if ball["in_play"]] or balls
                if pool:
                    chosen = max(pool, key=lambda ball: ball["score"])

            if chosen is not None:
                center = chosen["center"]
                if track is not None:
                    velocity = (
                        velocity[0] * 0.5 + (center[0] - track[0]) * 0.5,
                        velocity[1] * 0.5 + (center[1] - track[1]) * 0.5,
                    )
                track = center
                last_seen = t
                track_hits += 1
            elif last_seen is not None and t - last_seen > 2.0:
                track = None
                velocity = (0.0, 0.0)

            if balls:
                ball_frames += 1

            record = {
                "frame": frame_index,
                "t": round(t, 3),
                "balls": balls,
                "track": chosen,
                "track_state": list(track) if track is not None else None,
            }
            detections_file.write(json.dumps(record, ensure_ascii=False) + "\n")

            if chosen is not None:
                court = chosen.get("court") or [None, None]
                track_file.write(
                    f"{t:.3f},{chosen['center'][0]},{chosen['center'][1]},"
                    f"{court[0]},{court[1]},{chosen['score']},1\n"
                )
            else:
                track_file.write(f"{t:.3f},,,,,,0\n")

            sampled += 1
            if sampled % 50 == 0:
                processed_seconds = t - args.start
                print(
                    f"sampled={sampled} t={t:.1f}s balls={len(balls)} "
                    f"track={'yes' if chosen else 'no'} elapsed={time.time()-started:.0f}s",
                    flush=True,
                )
            frame_index += 1

    capture.release()
    elapsed = time.time() - started
    duration = (args.end if args.end is not None else total_frames / fps) - args.start
    meta = {
        "match_id": args.match_id,
        "model": args.model,
        "device": device,
        "tile": args.tile,
        "threshold": args.threshold,
        "sampled_fps": round(fps / step, 2),
        "frames_sampled": sampled,
        "duration_s": round(duration, 1),
        "elapsed_s": round(elapsed, 1),
        "frames_with_ball": ball_frames,
        "ball_frame_pct": round(100.0 * ball_frames / sampled, 1) if sampled else 0.0,
        "track_hits": track_hits,
        "track_pct": round(100.0 * track_hits / sampled, 1) if sampled else 0.0,
        "calibration_mode": calibration_mode,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
