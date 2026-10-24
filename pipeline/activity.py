from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from app.config import JOB_DIR
from app.db import get_match


def court_mask(points: list, width: int, height: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    if points:
        polygon = np.array(
            [
                [int(float(x) * width), int(float(y) * height)]
                for x, y in points
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(mask, [polygon], 255)
    else:
        mask[:] = 255
    return mask > 0


def build_activity(
    match_id: int,
    output: str = "activity.json",
    sample_fps: float = 1.0,
    width: int = 480,
) -> Path:
    match = get_match(match_id)
    if match is None:
        raise RuntimeError(f"partida {match_id} nao encontrada")
    video_path = Path(match["video_path"])
    if not video_path.is_file():
        raise RuntimeError("video nao encontrado")
    calibration = json.loads(match["calibration"]) if match["calibration"] else {}
    points = calibration.get("points") or []

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("nao foi possivel abrir o video")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or width)
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or width)
    scale = float(width) / max(1.0, float(frame_width))
    out_width = int(width)
    out_height = max(1, int(round(frame_height * scale)))
    mask = court_mask(points, out_width, out_height)
    mask_pixels = int(mask.sum())
    step = max(1, int(round(fps / max(0.1, sample_fps))))

    samples: list[dict] = []
    previous = None
    index = 0
    started = time.time()
    while True:
        if not capture.grab():
            break
        if index % step == 0:
            ok, frame = capture.retrieve()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (out_width, out_height), interpolation=cv2.INTER_AREA)
            if previous is not None:
                diff = cv2.absdiff(gray, previous)
                values = diff[mask]
                motion = float(values.mean()) if values.size else 0.0
                samples.append(
                    {
                        "t": round(index / fps, 2),
                        "motion": round(motion, 2),
                    }
                )
            previous = gray
        index += 1
    capture.release()

    path = Path(output)
    if not path.is_absolute():
        path = JOB_DIR / f"match-{match_id}" / path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "match_id": match_id,
        "sample_fps": round(fps / step, 3),
        "video_fps": round(fps, 3),
        "width": out_width,
        "height": out_height,
        "mask_pixels": mask_pixels,
        "calibrated": bool(points),
        "elapsed_s": round(time.time() - started, 1),
        "samples": samples,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(
        f"atividade: {len(samples)} amostras em {payload['elapsed_s']}s "
        f"({out_width}x{out_height}, mascara={mask_pixels}px)"
    )
    return path


def load_activity(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(payload, list):
        return {"samples": payload}
    return payload if isinstance(payload, dict) else None


def filter_windows(
    windows: list[dict],
    activity: dict | None,
    min_mean: float = 4.0,
) -> tuple[list[dict], int]:
    samples = (activity or {}).get("samples") or []
    if not samples:
        return windows, 0
    times = [float(sample.get("t", 0.0)) for sample in samples]
    values = [float(sample.get("motion", 0.0)) for sample in samples]
    kept: list[dict] = []
    dropped = 0
    for window in windows:
        start = float(window["start"])
        end = float(window["end"])
        selected = [
            value
            for sample_time, value in zip(times, values)
            if start <= sample_time <= end
        ]
        if not selected:
            kept.append(window)
            continue
        mean = sum(selected) / len(selected)
        maximum = max(selected)
        active_pct = sum(1 for value in selected if value >= min_mean) / len(selected)
        window["activity_mean"] = round(mean, 2)
        window["activity_max"] = round(maximum, 2)
        window["activity_active_pct"] = round(active_pct, 3)
        # Quadra vazia ou todos parados: a media de movimento no miolo da quadra
        # e baixa. Os clipes bons desta partida ficaram acima de 8; 4 e um corte
        # conservador que remove os trechos vazios sem descartar rallies lentos.
        if mean < min_mean:
            dropped += 1
            continue
        kept.append(window)
    return kept, dropped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", type=int, required=True)
    parser.add_argument("--output", default="activity.json")
    parser.add_argument("--sample-fps", type=float, default=1.0)
    parser.add_argument("--width", type=int, default=480)
    args = parser.parse_args()
    build_activity(
        args.match_id,
        output=args.output,
        sample_fps=args.sample_fps,
        width=args.width,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
