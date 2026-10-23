from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .constants import CALIBRATION_MODES, MANUAL_EVENT_KINDS


class LocalVideoIn(BaseModel):
    path: str
    title: str | None = None
    opponent: str = ""
    played_on: str = ""


class CalibrationIn(BaseModel):
    points: list[list[float]]
    mode: str = "full"

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, mode: str) -> str:
        if mode not in CALIBRATION_MODES:
            raise ValueError("modo de calibração inválido")
        return mode

    @field_validator("points")
    @classmethod
    def validate_points(cls, points: list[list[float]]) -> list[list[float]]:
        if len(points) != 4:
            raise ValueError("informe exatamente 4 pontos")
        for point in points:
            if len(point) != 2:
                raise ValueError("cada ponto deve ter duas coordenadas")
            x, y = point
            if not 0 <= x <= 1 or not 0 <= y <= 1:
                raise ValueError("coordenadas devem estar normalizadas entre 0 e 1")
        return points


class ManualEventIn(BaseModel):
    t: float = Field(ge=0)
    kind: str
    player_id: int | None = None
    set_no: int | None = Field(default=None, ge=1, le=5)
    rally_no: int | None = Field(default=None, ge=1)
    note: str = ""

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, kind: str) -> str:
        if kind not in MANUAL_EVENT_KINDS:
            raise ValueError("tipo de evento inválido")
        return kind


class ClipRejectIn(BaseModel):
    reason: str = "other"
    note: str = ""

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, reason: str) -> str:
        if reason not in {
            "dead_time",
            "ball_on_floor",
            "not_rally",
            "bad_cut",
            "half_rally",
            "duplicate",
            "other",
        }:
            raise ValueError("motivo de exclusão inválido")
        return reason

    @field_validator("note")
    @classmethod
    def clean_note(cls, note: str) -> str:
        return note.strip()[:500]


class ClipStarIn(BaseModel):
    starred: bool = True


class ClipStatusIn(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, status: str) -> str:
        if status not in {"new", "saved"}:
            raise ValueError("status deve ser new ou saved")
        return status


class PlayerIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    number: int | None = Field(default=None, ge=0, le=99)
    team: str = "home"

    @field_validator("name")
    @classmethod
    def clean_name(cls, name: str) -> str:
        name = name.strip()
        if not name:
            raise ValueError("nome obrigatório")
        return name

    @field_validator("team")
    @classmethod
    def validate_team(cls, team: str) -> str:
        if team not in {"home", "away"}:
            raise ValueError("equipe deve ser home ou away")
        return team
