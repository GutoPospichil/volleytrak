from __future__ import annotations

import torch
import torchvision
from transformers import AutoImageProcessor, AutoModelForObjectDetection


def load_detector(model_dir: str, device: str):
    processor = AutoImageProcessor.from_pretrained(model_dir, backend="torchvision")
    model = AutoModelForObjectDetection.from_pretrained(model_dir).to(device).eval()
    return model, processor


def tiles_for(width: int, height: int, tile: int, overlap: float = 0.25):
    if max(width, height) <= tile * 1.15:
        return [(0, 0, width, height)]
    stride = int(tile * (1 - overlap))
    xs = list(range(0, max(1, width - tile) + 1, stride))
    ys = list(range(0, max(1, height - tile) + 1, stride))
    if xs[-1] != width - tile:
        xs.append(max(0, width - tile))
    if ys[-1] != height - tile:
        ys.append(max(0, height - tile))
    tiles = [(x, y, min(width, x + tile), min(height, y + tile)) for y in ys for x in xs]
    tiles.append((0, 0, width, height))
    return tiles


def _cover(box, other) -> float:
    intersection_x = max(0, min(box[2], other[2]) - max(box[0], other[0]))
    intersection_y = max(0, min(box[3], other[3]) - max(box[1], other[1]))
    area = max(1e-6, (box[2] - box[0]) * (box[3] - box[1]))
    return intersection_x * intersection_y / area


def merge(detections, id2label, nms_iou: float = 0.5, contain: float = 0.85):
    final = []
    for label in set(item[5] for item in detections):
        group = [item for item in detections if item[5] == label]
        uncut = sorted([item for item in group if not item[6]], key=lambda item: -item[4])
        cut = sorted([item for item in group if item[6]], key=lambda item: -item[4])
        kept = []
        if uncut:
            boxes = torch.tensor([item[:4] for item in uncut])
            scores = torch.tensor([item[4] for item in uncut])
            for index in torchvision.ops.nms(boxes, scores, nms_iou).tolist():
                candidate = uncut[index]
                if any(_cover(candidate, other) > contain for other in kept):
                    continue
                kept.append(candidate)
        for candidate in cut:
            if any(_cover(candidate, other) > 0.4 for other in kept):
                continue
            kept.append(candidate)
        for x1, y1, x2, y2, score, _, _ in kept:
            final.append(
                {
                    "label": id2label[label],
                    "score": round(float(score), 3),
                    "box": [round(float(x1), 1), round(float(y1), 1), round(float(x2), 1), round(float(y2), 1)],
                }
            )
    return sorted(final, key=lambda item: -item["score"])


@torch.inference_mode()
def detect(
    model,
    processor,
    image,
    device: str,
    tile: int = 864,
    threshold: float = 0.3,
    nms_iou: float = 0.5,
    batch: int = 8,
    labels: set[str] | None = None,
    fp16: bool = False,
):
    width, height = image.size
    crops = tiles_for(width, height, tile)
    detections = []
    for start in range(0, len(crops), batch):
        chunk = crops[start:start + batch]
        images = [image.crop(box) for box in chunk]
        inputs = processor(images=images, return_tensors="pt").to(device)
        if fp16 and device != "cpu":
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                outputs = model(**inputs)
        else:
            outputs = model(**inputs)
        sizes = torch.tensor([(box[3] - box[1], box[2] - box[0]) for box in chunk])
        results = processor.post_process_object_detection(
            outputs, threshold=threshold, target_sizes=sizes
        )
        for result, box in zip(results, chunk):
            full = box == (0, 0, width, height)
            tile_width = box[2] - box[0]
            tile_height = box[3] - box[1]
            for score, label, candidate in zip(
                result["scores"].tolist(),
                result["labels"].tolist(),
                result["boxes"].tolist(),
            ):
                margin = 3
                cut = (not full) and (
                    (candidate[0] < margin and box[0] > 0)
                    or (candidate[1] < margin and box[1] > 0)
                    or (candidate[2] > tile_width - margin and box[2] < width)
                    or (candidate[3] > tile_height - margin and box[3] < height)
                )
                detections.append(
                    (
                        candidate[0] + box[0],
                        candidate[1] + box[1],
                        candidate[2] + box[0],
                        candidate[3] + box[1],
                        score,
                        label,
                        cut,
                    )
                )
    merged = merge(detections, model.config.id2label, nms_iou)
    if labels is not None:
        merged = [item for item in merged if item["label"] in labels]
    return merged
