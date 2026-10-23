from __future__ import annotations

import os
from pathlib import Path

from app.config import MODEL_DIR


class NullDetector:
    name = "none"
    warning = "Ultralytics/torch não instalados; pipeline rodou sem detecção."

    def infer(self, frame):
        return [], None


class YoloDetector:
    name = "ultralytics"

    def __init__(self, model_path: str | None = None, confidence: float = 0.25):
        from ultralytics import YOLO
        import torch

        torch.backends.cudnn.benchmark = True
        self.confidence = confidence
        self.device = 0 if torch.cuda.is_available() else "cpu"
        self.quantize = 16 if self.device != "cpu" else None
        default_model = MODEL_DIR / "yolov8n.pt"
        chosen = (
            model_path
            or os.getenv("VOLLEYTRAK_MODEL")
            or (str(default_model) if default_model.exists() else "yolov8n.pt")
        )
        self.model = YOLO(str(chosen))

    def infer(self, frame):
        results = self.model.track(
            frame,
            persist=True,
            classes=[0, 32],
            conf=self.confidence,
            iou=0.5,
            verbose=False,
            device=self.device,
            quantize=self.quantize,
            tracker="bytetrack.yaml",
        )
        result = results[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return [], None

        coordinates = boxes.xyxy.cpu().numpy()
        confidences = boxes.conf.cpu().numpy()
        classes = boxes.cls.cpu().numpy().astype(int)
        track_ids = (
            boxes.id.cpu().numpy().astype(int)
            if boxes.id is not None
            else [None] * len(coordinates)
        )

        persons = []
        balls = []
        for bbox, confidence, class_id, track_id in zip(
            coordinates, confidences, classes, track_ids
        ):
            left, top, right, bottom = (float(value) for value in bbox)
            item = {
                "bbox": [left, top, right, bottom],
                "conf": round(float(confidence), 3),
                "center": [(left + right) / 2.0, (top + bottom) / 2.0],
            }
            if class_id == 0:
                item["track_id"] = int(track_id) if track_id is not None else None
                persons.append(item)
            elif class_id == 32:
                balls.append(item)

        ball = max(balls, key=lambda item: item["conf"]) if balls else None
        return persons, ball


def build_detector():
    if os.getenv("VOLLEYTRAK_DETECTOR", "ultralytics").lower() == "none":
        return NullDetector()
    try:
        return YoloDetector()
    except Exception as exc:
        print(f"[aviso] detector indisponível: {exc}")
        return NullDetector()
