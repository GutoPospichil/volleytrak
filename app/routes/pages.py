from __future__ import annotations

import json
from collections import Counter

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from ..config import JOB_DIR
from ..constants import (
    CALIBRATION_MODES,
    CLIP_REJECTION_CANONICAL,
    CLIP_REJECTION_DETAIL_LABELS,
    CLIP_REJECTION_LABELS,
    EVENT_KIND_LABELS,
    MANUAL_EVENT_KINDS,
    STATUS_LABELS,
)
from ..db import (
    clip_edit_stats,
    get_match,
    learning_stats,
    list_recent_clip_edits,
    list_recent_learning_examples,
    list_clip_rejections,
    list_clips,
    list_events,
    list_matches,
    list_players,
)
from ..serializers import event_dict, match_dict, player_dict
from ..templating import templates
from ..timeline import build_timeline

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    matches = [match_dict(row) for row in list_matches()]
    return templates.TemplateResponse(
        request,
        "index.html",
        {"matches": matches, "status_labels": STATUS_LABELS},
    )


@router.get("/matches/{match_id}", response_class=HTMLResponse)
def match_detail(request: Request, match_id: int, tab: str = "new"):
    row = get_match(match_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Partida nǜo encontrada")
    players = [player_dict(player) for player in list_players()]
    events = [event_dict(event) for event in list_events(match_id)]
    active_tab = "saved" if tab == "saved" else "new"
    highlight_path = JOB_DIR / f"match-{match_id}" / "highlight.mp4"
    rejections = list_clip_rejections(match_id)
    rejection_counts = Counter(
        CLIP_REJECTION_CANONICAL.get(row["reason"] or "other", row["reason"] or "other")
        for row in rejections
    )
    rejection_detail_counts = Counter(
        row["detail"] for row in rejections if row["detail"]
    )
    match_data = match_dict(row)

    def enrich_clip(clip: dict) -> dict:
        payload = {}
        if clip.get("features"):
            try:
                payload = json.loads(clip["features"])
            except (TypeError, json.JSONDecodeError):
                payload = {}
        ranker_score = payload.get("ranker_score")
        if isinstance(ranker_score, (int, float)):
            confidence = float(ranker_score)
        else:
            confidence = float(clip.get("score") or 0.0)
        clip["ranker_score"] = ranker_score
        clip["uncertainty"] = round(abs(confidence - 50.0) / 50.0, 3)
        clip["edited"] = bool(payload.get("edited"))
        clip["edited_score"] = payload.get("edited_score")
        clip["generated_score"] = payload.get("generated_score", clip.get("score"))
        clip["score_delta"] = payload.get("score_delta")
        clip["fair_delta"] = payload.get("fair_delta")
        return clip

    clips_new = [enrich_clip(dict(clip)) for clip in list_clips(match_id, "new")]
    clips_saved = [enrich_clip(dict(clip)) for clip in list_clips(match_id, "saved")]
    all_clips = clips_new + clips_saved
    duration = 0.0
    if match_data.get("result"):
        duration = float((match_data["result"].get("summary") or {}).get("duration_s") or 0.0)
    if duration <= 0 and all_clips:
        duration = max(float(clip["end"]) for clip in all_clips)
    timeline = build_timeline(all_clips, duration) if all_clips and duration > 0 else None
    saved_scores = [
        float(clip["saved_score"])
        for clip in clips_saved
        if clip.get("saved_score") is not None
    ]
    saved_average = (
        round(sum(saved_scores) / len(saved_scores), 1) if saved_scores else None
    )
    feedback_profile = None
    profile_path = JOB_DIR / f"match-{match_id}" / "feedback_profile.json"
    if profile_path.is_file():
        try:
            feedback_profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            feedback_profile = None
    ranker_info = None
    ranker_path = JOB_DIR.parent / "feedback_ranker.json"
    if ranker_path.is_file():
        try:
            ranker_info = json.loads(ranker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            ranker_info = None
    return templates.TemplateResponse(
        request,
        "match.html",
        {
            "match": match_data,
            "events": events,
            "players": players,
            "players_map": {player["id"]: player for player in players},
            "kinds": MANUAL_EVENT_KINDS,
            "kind_labels": EVENT_KIND_LABELS,
            "status_labels": STATUS_LABELS,
            "calibration_modes": CALIBRATION_MODES,
            "clips_new": clips_new,
            "clips_saved": clips_saved,
            "timeline": timeline,
            "saved_average": saved_average,
            "active_tab": active_tab,
            "highlight_available": highlight_path.is_file(),
            "rejection_counts": dict(rejection_counts),
            "rejection_total": len(rejections),
            "rejection_labels": CLIP_REJECTION_LABELS,
            "rejection_details": CLIP_REJECTION_DETAIL_LABELS,
            "rejection_detail_counts": dict(rejection_detail_counts),
            "feedback_profile": feedback_profile,
            "ranker_info": ranker_info,
        },
    )


@router.get("/matches/{match_id}/calibrate", response_class=HTMLResponse)
def calibrate(request: Request, match_id: int):
    row = get_match(match_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Partida não encontrada")
    return templates.TemplateResponse(
        request,
        "calibrate.html",
        {"match": match_dict(row), "calibration_modes": CALIBRATION_MODES},
    )


@router.get("/aprendizado", response_class=HTMLResponse)
def learning_page(request: Request):
    stats = learning_stats()
    reasons: Counter[str] = Counter()
    for reason, count in stats.get("reasons", {}).items():
        canonical = CLIP_REJECTION_CANONICAL.get(reason or "other", reason or "other")
        reasons[canonical] += int(count)
    stats["reasons"] = dict(reasons)
    recent = [dict(row) for row in list_recent_learning_examples(20)]
    recent_edits = [dict(row) for row in list_recent_clip_edits(12)]
    for row in recent_edits:
        reason = row["reason"] or "other"
        canonical = CLIP_REJECTION_CANONICAL.get(reason, reason)
        row["reason_label"] = CLIP_REJECTION_LABELS.get(canonical, canonical)
        row["detail_label"] = CLIP_REJECTION_DETAIL_LABELS.get(
            row["detail"] or "", row["detail"] or ""
        )
        try:
            row["features_data"] = json.loads(row["features"]) if row["features"] else {}
        except (TypeError, json.JSONDecodeError):
            row["features_data"] = {}
    for row in recent:
        canonical = CLIP_REJECTION_CANONICAL.get(
            row["reason"] or "other", row["reason"] or "other"
        )
        row["reason_label"] = CLIP_REJECTION_LABELS.get(canonical, canonical)
        try:
            row["features_data"] = json.loads(row["features"]) if row["features"] else {}
        except (TypeError, json.JSONDecodeError):
            row["features_data"] = {}
    ranker_info = None
    ranker_path = JOB_DIR.parent / "feedback_ranker.json"
    if ranker_path.is_file():
        try:
            ranker_info = json.loads(ranker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            ranker_info = None
    return templates.TemplateResponse(
        request,
        "learning.html",
        {
            "stats": stats,
            "recent": recent,
            "ranker_info": ranker_info,
            "rejection_labels": CLIP_REJECTION_LABELS,
            "rejection_details": CLIP_REJECTION_DETAIL_LABELS,
            "edit_stats": clip_edit_stats(),
            "recent_edits": recent_edits,
        },
    )


@router.get("/players", response_class=HTMLResponse)
def players_page(request: Request):
    players = [player_dict(player) for player in list_players()]
    return templates.TemplateResponse(
        request,
        "players.html",
        {"players": players},
    )
