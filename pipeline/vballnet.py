from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from app.config import JOB_DIR, MODEL_DIR
from app.db import get_match
from pipeline.calibration import homography_from_points, project_point

INPUT_WIDTH = 512
INPUT_HEIGHT = 288
SEQUENCE = 9


def load_session(model_path: Path) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    return ort.InferenceSession(
        str(model_path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )


def preprocess(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (INPUT_WIDTH, INPUT_HEIGHT))
    return gray.astype(np.float32) / 255.0


def find_ball(heatmap: np.ndarray, threshold: float) -> tuple[int, int, float] | None:
    score = float(heatmap.max())
    if score < threshold:
        return None
    y, x = np.unravel_index(np.argmax(heatmap), heatmap.shape)
    return int(x), int(y), score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", type=int, required=True)
    parser.add_argument(
        "--model",
        default=str(MODEL_DIR / "vballnet" / "VballNetV1a_seq9_grayscale_gru_best.onnx"),
    )
    parser.add_argument("--output", default="ball_vballnet.jsonl")
    parser.add_argument("--threshold", type=float, default=0.4)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--duration", type=float, default=0.0)
    args = parser.parse_args()

    match = get_match(args.match_id)
    if match is None:
        print(f"partida {args.match_id} não encontrada")
        return 1
    video_path = Path(match["video_path"])
    if not video_path.is_file():
        print("vídeo não encontrado")
        return 1
    model_path = Path(args.model)
    if not model_path.is_file():
        print("modelo VballNet não encontrado")
        return 1

    calibration = json.loads(match["calibration"]) if match["calibration"] else None
    calibration_points = calibration.get("points") if calibration else None
    calibration_mode = calibration.get("mode", "full") if calibration else "full"

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        print("não foi possível abrir o vídeo")
        return 1
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    matrix = None
    if calibration_points:
        matrix = homography_from_points(
            calibration_points, (width, height), calibration_mode
        )

    start_frame = max(0, int(args.start * fps))
    end_frame = total_frames
    if args.duration > 0:
        end_frame = min(end_frame, start_frame + int(args.duration * fps))
    if start_frame > 0:
        capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    session = load_session(model_path)
    input_name = session.get_inputs()[0].name

    job_dir = JOB_DIR / f"match-{args.match_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    output_path = job_dir / args.output
    meta_path = job_dir / "ball_vballnet.json"

    started = time.time()
    frame_index = start_frame
    processed = 0
    with_ball = 0
    blocks = 0
    with output_path.open("w", encoding="utf-8") as handle:
        while frame_index < end_frame:
            block: list[tuple[int, np.ndarray]] = []
            for _ in range(SEQUENCE):
                if frame_index >= end_frame:
                    break
                ok, frame = capture.read()
                if not ok:
                    break
                block.append((frame_index, frame))
                frame_index += 1
            if not block:
                break

            padded = [frame for _, frame in block]
            while len(padded) < SEQUENCE:
                padded.append(padded[-1])
            tensor = np.stack([preprocess(frame) for frame in padded], axis=0)[None, ...]
            heatmaps = session.run(None, {input_name: tensor})[0][0]
            blocks += 1

            for frame_pos, (global_frame, _) in enumerate(block):
                heatmap = heatmaps[frame_pos]
                found = find_ball(heatmap, args.threshold)
                balls = []
                if found is not None:
                    x_in, y_in, score = found
                    x = x_in * width / INPUT_WIDTH
                    y = y_in * height / INPUT_HEIGHT
                    court = project_point(matrix, (x, y)) if matrix is not None else None
                    if court is None or (
                        -2.5 <= court[0] <= 20.5 and -2.5 <= court[1] <= 11.5
                    ):
                        balls.append(
                            {
                                "center": [round(x, 1), round(y, 1)],
                                "box": [
                                    round(x - 16, 1),
                                    round(y - 16, 1),
                                    round(x + 16, 1),
                                    round(y + 16, 1),
                                ],
                                "score": round(score, 4),
                                "court": [round(court[0], 2), round(court[1], 2)]
                                if court
                                else None,
                            }
                        )
                        with_ball += 1
                record = {
                    "frame": global_frame,
                    "t": round(global_frame / fps, 3),
                    "balls": balls,
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                processed += 1
                if processed % 300 == 0:
                    print(
                        f"processed={processed} t={global_frame / fps:.1f}s "
                        f"ball_pct={with_ball / processed * 100:.1f} "
                        f"elapsed={time.time() - started:.0f}s",
                        flush=True,
                    )

    capture.release()
    elapsed = time.time() - started
    summary = {
        "match_id": args.match_id,
        "model": str(model_path),
        "device": "cpu",
        "threshold": args.threshold,
        "frames": processed,
        "frames_with_ball": with_ball,
        "ball_frame_pct": round(with_ball / processed * 100, 1) if processed else 0.0,
        "fps": round(fps, 3),
        "elapsed_s": round(elapsed, 1),
        "blocks": blocks,
        "output": str(output_path),
    }
    meta_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
