from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.config import JOB_DIR
from app.db import get_setting, list_clips


def configured_clip_dir() -> Path | None:
    value = get_setting("clip_output_dir")
    if not value:
        return None
    return Path(value)


def clip_dir_for_match(match_id: int) -> Path:
    base = configured_clip_dir()
    if base is not None:
        return base / f"match-{match_id}"
    return JOB_DIR / f"match-{match_id}" / "clips"


def clip_folder_for_match(match_id: int) -> Path:
    target = clip_dir_for_match(match_id)
    try:
        if target.is_dir() and any(target.iterdir()):
            return target
    except OSError:
        pass
    clips = list_clips(match_id)
    parents = Counter(
        str(Path(clip["path"]).parent)
        for clip in clips
        if clip["path"]
    )
    if parents:
        return Path(parents.most_common(1)[0][0])
    return target
