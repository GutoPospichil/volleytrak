from __future__ import annotations

import json
import mimetypes
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from ..config import (
    JOB_DIR,
    MAX_UPLOAD_BYTES,
    ROOT,
    VIDEO_DIR,
    VIDEO_EXTENSIONS,
    ensure_dirs,
)
from collections import Counter

from ..db import (
    add_clip_rejection,
    add_event,
    add_player,
    create_match,
    delete_clip,
    delete_event,
    delete_match,
    delete_player,
    get_clip,
    get_event,
    get_match,
    get_player,
    list_clip_rejections,
    list_clips,
    list_events,
    list_matches,
    list_players,
    set_clip_starred,
    set_clip_status,
    update_match,
)
from ..schemas import (
    CalibrationIn,
    ClipRejectIn,
    ClipStarIn,
    ClipStatusIn,
    LocalVideoIn,
    ManualEventIn,
    PlayerIn,
)
from ..serializers import event_dict, match_dict, player_dict
from pipeline.feedback import build_profile_for_match

router = APIRouter()


def _require_match(match_id: int):
    row = get_match(match_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Partida não encontrada")
    return row


def _invalidate_highlight(match_id: int) -> None:
    (JOB_DIR / f"match-{match_id}" / "highlight.mp4").unlink(missing_ok=True)


@router.get("/matches")
def get_matches():
    return [match_dict(row) for row in list_matches()]


@router.get("/matches/{match_id}")
def get_match_details(match_id: int):
    return match_dict(_require_match(match_id))


@router.post("/matches")
async def upload_match(
    file: UploadFile = File(...),
    title: str = Form(""),
    opponent: str = Form(""),
    played_on: str = Form(""),
    whistle_mode: str = Form("with"),
):
    if whistle_mode not in {"with", "without"}:
        raise HTTPException(status_code=400, detail="Modo de apito inválido")
    ensure_dirs()
    original = Path(file.filename or "video.mp4")
    extension = original.suffix.lower()
    if extension not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato de vídeo não suportado")

    filename = f"{uuid4().hex}{extension}"
    destination = VIDEO_DIR / filename
    size = 0
    try:
        with destination.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Arquivo acima do limite")
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    match_title = title.strip() or original.stem
    match_id = create_match(
        match_title,
        str(destination),
        source="upload",
        opponent=opponent.strip(),
        played_on=played_on.strip(),
        whistle_mode=whistle_mode,
    )
    return match_dict(get_match(match_id))


@router.post("/matches/local")
def register_local_video(payload: LocalVideoIn):
    path = Path(payload.path).expanduser()
    if not path.is_file():
        raise HTTPException(status_code=400, detail="Arquivo não encontrado")
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato de vídeo não suportado")
    match_title = (payload.title or "").strip() or path.stem
    match_id = create_match(
        match_title,
        str(path.resolve()),
        source="local",
        opponent=payload.opponent.strip(),
        played_on=payload.played_on.strip(),
        whistle_mode=payload.whistle_mode,
    )
    return match_dict(get_match(match_id))


@router.delete("/matches/{match_id}")
def remove_match(match_id: int):
    row = _require_match(match_id)
    if row["status"] == "processing":
        raise HTTPException(
            status_code=409, detail="Aguarde o processamento terminar antes de excluir"
        )
    video_path = Path(row["video_path"])
    if row["source"] == "upload":
        try:
            video_path.resolve().relative_to(VIDEO_DIR.resolve())
            video_path.unlink(missing_ok=True)
        except ValueError:
            pass
    annotated = row["annotated_path"]
    if annotated:
        Path(annotated).unlink(missing_ok=True)
    shutil.rmtree(JOB_DIR / f"match-{match_id}", ignore_errors=True)
    delete_match(match_id)
    return {"ok": True}


@router.post("/matches/{match_id}/calibration")
def save_calibration(match_id: int, payload: CalibrationIn):
    _require_match(match_id)
    calibration = json.dumps(
        {"mode": payload.mode, "points": payload.points}, ensure_ascii=False
    )
    update_match(match_id, calibration=calibration)
    return {"ok": True, "mode": payload.mode, "points": payload.points}


@router.post("/matches/{match_id}/process")
def process_match(match_id: int):
    row = _require_match(match_id)
    if row["status"] == "processing":
        raise HTTPException(status_code=409, detail="Partida já está em processamento")
    if not Path(row["video_path"]).is_file():
        raise HTTPException(status_code=400, detail="Arquivo de vídeo não encontrado")

    job_dir = JOB_DIR / f"match-{match_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    log_path = job_dir / "run.log"
    log_file = log_path.open("ab")

    update_match(
        match_id,
        status="processing",
        progress=0,
        message="Iniciando pipeline...",
        result=None,
        annotated_path=None,
    )

    command = [sys.executable, "-m", "pipeline.run", "--match-id", str(match_id)]
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    environment.setdefault("PYTHONIOENCODING", "utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=environment,
            creationflags=flags,
        )
    except Exception as exc:
        update_match(match_id, status="error", message=f"Falha ao iniciar pipeline: {exc}")
        raise HTTPException(status_code=500, detail="Não foi possível iniciar o processamento")
    finally:
        log_file.close()

    return {"ok": True, "match_id": match_id}


@router.get("/matches/{match_id}/frame")
def get_frame(match_id: int, t: float = 0.0):
    row = _require_match(match_id)
    path = Path(row["video_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise HTTPException(status_code=400, detail="Não foi possível abrir o vídeo")
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(t * fps)))
    ok, frame = capture.read()
    if not ok:
        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, frame = capture.read()
    capture.release()
    if not ok:
        raise HTTPException(status_code=404, detail="Frame indisponível")

    height, width = frame.shape[:2]
    max_width = 1600
    if width > max_width:
        scale = max_width / width
        frame = cv2.resize(frame, (max_width, int(height * scale)))

    success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not success:
        raise HTTPException(status_code=500, detail="Falha ao gerar frame")
    return Response(
        content=buffer.tobytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/matches/{match_id}/video")
def get_video(match_id: int):
    row = _require_match(match_id)
    path = Path(row["video_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")
    media_type = mimetypes.guess_type(path.name)[0] or "video/mp4"
    return FileResponse(path, media_type=media_type)




@router.get("/matches/{match_id}/detections")
def get_detections(match_id: int):
    _require_match(match_id)
    path = JOB_DIR / f"match-{match_id}" / "detections.jsonl"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Detecções não disponíveis")
    return FileResponse(path, media_type="application/x-ndjson", filename=path.name)


@router.get("/matches/{match_id}/events")
def get_events(match_id: int):
    _require_match(match_id)
    return [event_dict(row) for row in list_events(match_id)]


@router.post("/matches/{match_id}/events")
def create_manual_event(match_id: int, payload: ManualEventIn):
    _require_match(match_id)
    if payload.player_id is not None and get_player(payload.player_id) is None:
        raise HTTPException(status_code=400, detail="Jogador não encontrado")
    event_id = add_event(
        match_id,
        t=payload.t,
        kind=payload.kind,
        player_id=payload.player_id,
        set_no=payload.set_no,
        rally_no=payload.rally_no,
        note=payload.note.strip(),
        source="manual",
    )
    return event_dict(get_event(event_id))


@router.delete("/events/{event_id}")
def remove_event(event_id: int):
    if get_event(event_id) is None:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    delete_event(event_id)
    return {"ok": True}


@router.get("/matches/{match_id}/clips")
def get_clips(match_id: int, status: str | None = None):
    _require_match(match_id)
    if status == "all":
        status = None
    if status is not None and status not in {"new", "saved"}:
        raise HTTPException(status_code=400, detail="status inválido")
    return [dict(row) for row in list_clips(match_id, status=status)]


@router.get("/matches/{match_id}/clips/{clip_id}")
def get_clip_video(match_id: int, clip_id: int):
    clip = get_clip(clip_id)
    if clip is None or clip["match_id"] != match_id:
        raise HTTPException(status_code=404, detail="Clipe não encontrado")
    path = Path(clip["path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo do clipe não encontrado")
    return FileResponse(path, media_type="video/mp4")


@router.get("/matches/{match_id}/clips/{clip_id}/thumb")
def get_clip_thumb(match_id: int, clip_id: int):
    clip = get_clip(clip_id)
    if clip is None or clip["match_id"] != match_id or not clip["thumb"]:
        raise HTTPException(status_code=404, detail="Miniatura não encontrada")
    path = Path(clip["thumb"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Miniatura não encontrada")
    return FileResponse(path, media_type="image/jpeg")


@router.patch("/clips/{clip_id}")
def update_clip_status(clip_id: int, payload: ClipStatusIn):
    clip = get_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clipe não encontrado")
    set_clip_status(clip_id, payload.status)
    _invalidate_highlight(clip["match_id"])
    return {"ok": True, "id": clip_id, "status": payload.status}


def _clip_features(clip) -> dict:
    features = {}
    if clip["features"]:
        try:
            features = json.loads(clip["features"])
        except (TypeError, json.JSONDecodeError):
            features = {}
    features.update(
        {
            "source": clip["source"],
            "score": clip["score"],
            "saved_score": clip["saved_score"],
            "starred": bool(clip["starred"]),
            "duration": clip["duration"],
        }
    )
    return features


def _reject_clip(clip, reason: str, note: str, detail: str = "") -> None:
    add_clip_rejection(
        clip["match_id"],
        clip["start"],
        clip["end"],
        reason=reason,
        detail=detail,
        note=note,
        features=_clip_features(clip),
    )
    Path(clip["path"]).unlink(missing_ok=True)
    if clip["thumb"]:
        Path(clip["thumb"]).unlink(missing_ok=True)
    delete_clip(clip["id"])
    _invalidate_highlight(clip["match_id"])
    build_profile_for_match(clip["match_id"])


@router.post("/clips/{clip_id}/star")
def star_clip(clip_id: int, payload: ClipStarIn):
    clip = get_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clipe não encontrado")
    set_clip_starred(clip_id, payload.starred)
    if payload.starred and clip["status"] == "new":
        set_clip_status(clip_id, "saved")
    _invalidate_highlight(clip["match_id"])
    if payload.starred or clip["status"] == "saved":
        subprocess.run(
            [sys.executable, "-m", "pipeline.clip_score", "--match-id", str(clip["match_id"])],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
    return {"ok": True, "starred": payload.starred}


@router.post("/clips/{clip_id}/reject")
def reject_clip(clip_id: int, payload: ClipRejectIn):
    clip = get_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clipe não encontrado")
    _reject_clip(clip, payload.reason, payload.note, payload.detail)
    return {"ok": True, "reason": payload.reason, "detail": payload.detail}


@router.delete("/clips/{clip_id}")
def remove_clip(clip_id: int):
    clip = get_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clipe não encontrado")
    _reject_clip(clip, "other", "", "")
    return {"ok": True}


@router.get("/matches/{match_id}/feedback")
def get_feedback(match_id: int):
    _require_match(match_id)
    rows = [dict(row) for row in list_clip_rejections(match_id)]
    counts = Counter(row["reason"] or "other" for row in rows)
    return {"total": len(rows), "counts": dict(counts), "rejections": rows}


@router.post("/matches/{match_id}/highlight")
def build_highlight(match_id: int):
    _require_match(match_id)
    clips = [clip for clip in list_clips(match_id, status="saved") if Path(clip["path"]).is_file()]
    clips.sort(key=lambda clip: (0 if clip["starred"] else 1, clip["start"]))
    if not clips:
        raise HTTPException(status_code=400, detail="Nenhum clipe salvo para montar o highlight")

    job_dir = JOB_DIR / f"match-{match_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    concat_path = job_dir / "highlight.txt"
    output_path = job_dir / "highlight.mp4"
    temp_path = job_dir / "highlight.tmp.mp4"
    lines = [
        "file '"
        + Path(clip["path"]).as_posix().replace("'", "'\\''")
        + "'"
        for clip in clips
    ]
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(temp_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, timeout=900)
        if result.returncode != 0 or not temp_path.is_file() or temp_path.stat().st_size == 0:
            fallback = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                str(temp_path),
            ]
            subprocess.run(fallback, check=True, capture_output=True, timeout=900)
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Falha ao montar highlight: {exc}")

    temp_path.replace(output_path)
    return {
        "ok": True,
        "url": f"/api/matches/{match_id}/highlight",
        "count": len(clips),
    }


@router.get("/matches/{match_id}/highlight")
def get_highlight(match_id: int):
    _require_match(match_id)
    path = JOB_DIR / f"match-{match_id}" / "highlight.mp4"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Highlight não disponível")
    return FileResponse(path, media_type="video/mp4", filename=f"highlight-{match_id}.mp4")


@router.post("/matches/{match_id}/clips/score-saved")
def score_saved_clips(match_id: int):
    _require_match(match_id)
    if not list_clips(match_id, "saved"):
        raise HTTPException(status_code=400, detail="Nenhum clipe salvo para pontuar")
    result = subprocess.run(
        [sys.executable, "-m", "pipeline.clip_score", "--match-id", str(match_id)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail="Falha ao calcular as notas")
    return {"ok": True, "output": result.stdout.strip()}


@router.post("/matches/{match_id}/clips/process")
def process_clips(match_id: int):
    row = _require_match(match_id)
    if row["status"] == "processing":
        raise HTTPException(status_code=409, detail="Já existe processamento em andamento")
    if not Path(row["video_path"]).is_file():
        raise HTTPException(status_code=400, detail="Arquivo de vídeo não encontrado")
    if not row["calibration"]:
        raise HTTPException(status_code=400, detail="Calibre a quadra antes de processar os clipes")

    job_dir = JOB_DIR / f"match-{match_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    log_file = (job_dir / "clip_job.log").open("ab")
    update_match(
        match_id,
        status="processing",
        progress=0,
        message="Iniciando geração de clipes...",
        result=None,
        annotated_path=None,
    )
    command = [
        sys.executable,
        "-m",
        "pipeline.clip_job",
        "--match-id",
        str(match_id),
    ]
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=environment,
            creationflags=flags,
        )
    except Exception as exc:
        update_match(match_id, status="error", message=f"Falha ao iniciar clipes: {exc}")
        raise HTTPException(status_code=500, detail="Não foi possível iniciar a geração de clipes")
    finally:
        log_file.close()
    return {"ok": True, "match_id": match_id}


@router.post("/matches/{match_id}/clips/generate")
def generate_clips(match_id: int):
    _require_match(match_id)
    job_dir = JOB_DIR / f"match-{match_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    log_file = (job_dir / "clips.log").open("ab")
    command = [sys.executable, "-m", "pipeline.clips", "--match-id", str(match_id)]
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=environment,
            creationflags=flags,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao iniciar clipes: {exc}")
    finally:
        log_file.close()
    return {"ok": True}


@router.get("/players")
def get_players():
    return [player_dict(row) for row in list_players()]


@router.post("/players")
def create_player(payload: PlayerIn):
    player_id = add_player(payload.name, payload.number, payload.team)
    return player_dict(get_player(player_id))


@router.delete("/players/{player_id}")
def remove_player(player_id: int):
    if get_player(player_id) is None:
        raise HTTPException(status_code=404, detail="Jogador não encontrado")
    delete_player(player_id)
    return {"ok": True}
