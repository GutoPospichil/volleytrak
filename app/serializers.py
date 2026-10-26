from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def parse_json(value: Any) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None


def match_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    match = dict(row)
    match["calibration"] = parse_json(match.get("calibration"))
    match["result"] = parse_json(match.get("result"))
    video_path = match.get("video_path") or ""
    match["video_available"] = bool(video_path) and Path(video_path).is_file()
    return match


def event_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    event = dict(row)
    event["data"] = parse_json(event.get("data"))
    return event


def player_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)
