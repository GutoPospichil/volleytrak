from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("VOLLEYTRAK_DATA", str(ROOT / "data")))
VIDEO_DIR = DATA_DIR / "videos"
JOB_DIR = DATA_DIR / "jobs"
MODEL_DIR = DATA_DIR / "models"
DB_PATH = DATA_DIR / "app.db"

COURT_LENGTH_M = 18.0
COURT_WIDTH_M = 9.0

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}

MAX_UPLOAD_BYTES = int(os.getenv("VOLLEYTRAK_MAX_UPLOAD_GB", "20")) * 1024**3

STATIC_DIR = ROOT / "app" / "static"
TEMPLATE_DIR = ROOT / "app" / "templates"


def ensure_dirs() -> None:
    for path in (DATA_DIR, VIDEO_DIR, JOB_DIR, MODEL_DIR):
        path.mkdir(parents=True, exist_ok=True)
