from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import cv2

from app.config import JOB_DIR
from app.db import add_event, clear_auto_events, get_match, init_db, update_match
from pipeline.calibration import (
    homography_from_points,
    image_court_polygon,
    inside_court,
    point_in_polygon,
    project_foot,
    project_point,
)
from pipeline.detect import build_detector
from pipeline.events import derive_touches


def point_in_bbox(
    point: tuple[float, float], bbox: list[float], margin: float = 0.08
) -> bool:
    left, top, right, bottom = bbox
    width = right - left
    height = bottom - top
    return (
        left - width * margin <= point[0] <= right + width * margin
        and top - height * margin <= point[1] <= bottom + height * margin
    )




def run_pipeline(match_id: int, match) -> None:
    video_path = Path(match["video_path"])
    if not video_path.is_file():
        raise FileNotFoundError("arquivo de vídeo não encontrado")

    job_dir = JOB_DIR / f"match-{match_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    detections_path = job_dir / "detections.jsonl"

    calibration = json.loads(match["calibration"]) if match["calibration"] else None
    calibration_points = calibration.get("points") if calibration else None
    calibration_mode = calibration.get("mode", "full") if calibration else "full"

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("não foi possível abrir o vídeo")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    stride = max(1, int(os.getenv("VOLLEYTRAK_STRIDE", "2")))

    detector = build_detector()
    clear_auto_events(match_id)
    update_match(match_id, status="processing", progress=0, message="Carregando v��deo...")
    print(f"detector={detector.name} fps={fps:.2f} stride={stride} frames={total_frames}")

    matrix = None
    court_polygon = None
    if calibration_points and frame_width and frame_height:
        matrix = homography_from_points(
            calibration_points, (frame_width, frame_height), calibration_mode
        )
        court_polygon = image_court_polygon(
            calibration_points,
            (frame_width, frame_height),
            calibration_mode,
            margin=0.0,
        )
    frame_index = 0
    processed = 0
    person_hits = 0
    off_court_hits = 0
    ball_hits = 0
    track_ids: set[int] = set()
    touch_candidates: list[dict] = []
    last_progress = 0.0
    started = time.time()

    with detections_path.open("w", encoding="utf-8") as detections_file:
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if frame_index % stride != 0:
                    frame_index += 1
                    continue

                timestamp = frame_index / fps
                persons, ball = detector.infer(frame)

                on_court_persons = []
                for person in persons:
                    person["court"] = project_foot(matrix, person["bbox"])
                    bbox = person["bbox"]
                    foot = ((bbox[0] + bbox[2]) / 2.0, bbox[3])
                    person["on_court"] = matrix is None or (
                        person["court"] is not None
                        and inside_court(person["court"], margin=0.3)
                        and point_in_polygon(court_polygon, foot)
                    )
                    if not person["on_court"]:
                        person["court"] = None
                        off_court_hits += 1
                        continue
                    on_court_persons.append(person)
                    if person.get("track_id") is not None:
                        track_ids.add(int(person["track_id"]))
                    person_hits += 1

                if ball is not None:
                    ball["court"] = project_point(matrix, tuple(ball["center"]))
                    if ball["court"] is not None and not inside_court(
                        ball["court"], margin=2.0
                    ):
                        ball["court"] = None
                    ball_hits += 1
                    for person in on_court_persons:
                        if point_in_bbox(tuple(ball["center"]), person["bbox"]):
                            if person.get("track_id") is not None:
                                touch_candidates.append(
                                    {
                                        "t": round(timestamp, 3),
                                        "track_id": int(person["track_id"]),
                                        "court": ball["court"],
                                    }
                                )
                            break

                record = {
                    "frame": frame_index,
                    "t": round(timestamp, 3),
                    "persons": persons,
                    "ball": ball,
                }
                detections_file.write(
                    json.dumps(record, ensure_ascii=False) + "\n"
                )
                processed += 1

                now = time.time()
                if now - last_progress >= 2.0:
                    if total_frames > 0:
                        progress = 99.0 * frame_index / total_frames
                    else:
                        progress = min(99.0, processed / 10.0)
                    update_match(
                        match_id,
                        progress=round(min(progress, 99.0), 1),
                        message=f"{processed} frames processados",
                    )
                    last_progress = now

                frame_index += 1
        finally:
            capture.release()

    if processed == 0:
        raise RuntimeError("nenhum frame p��de ser processado")

    touches = derive_touches(touch_candidates)
    for touch in touches:
        add_event(
            match_id,
            t=touch["t"],
            kind="touch",
            data={"track_id": touch["track_id"], "court": touch.get("court")},
            source="auto",
        )

    elapsed = time.time() - started
    duration = total_frames / fps if total_frames > 0 else None
    ball_visibility = round(100.0 * ball_hits / processed, 1) if processed else 0.0

    warnings = []
    detector_warning = getattr(detector, "warning", None)
    if detector_warning:
        warnings.append(detector_warning)
    if matrix is None:
        warnings.append("Quadra não calibrada: posições em metros não foram calculadas.")
    if detector.name != "none" and ball_visibility < 30:
        warnings.append(
            "Bola detectada em menos de 30% dos frames; o modelo COCO yolov8n é fraco para vôlei."
        )
    warnings.append(
        "Toques automáticos são provisórios (heurística de proximidade) e precisam de revisão."
    )

    summary = {
        "frames_total": total_frames,
        "frames_processed": processed,
        "fps": round(fps, 2),
        "stride": stride,
        "duration_s": round(duration, 1) if duration is not None else None,
        "persons_detected": person_hits,
        "off_court_detected": off_court_hits,
        "ball_detected": ball_hits,
        "ball_visibility_pct": ball_visibility,
        "unique_person_tracks": len(track_ids),
        "tentative_touches": len(touches),
        "calibrated": matrix is not None,
        "calibration_mode": calibration_mode,
        "detector": detector.name,
        "elapsed_s": round(elapsed, 1),
    }

    result = {
        "summary": summary,
        "warnings": warnings,
        "files": {
            "detections": detections_path.name,
            "log": "run.log",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    update_match(
        match_id,
        status="done",
        progress=100,
        message="Processamento concluído",
        result=json.dumps(result, ensure_ascii=False),
        annotated_path=None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", type=int, required=True)
    args = parser.parse_args()

    init_db()
    match = get_match(args.match_id)
    if match is None:
        print(f"partida {args.match_id} não encontrada")
        return 1

    try:
        run_pipeline(args.match_id, match)
    except Exception as exc:
        traceback.print_exc()
        update_match(
            args.match_id,
            status="error",
            message=f"{type(exc).__name__}: {exc}"[:500],
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
