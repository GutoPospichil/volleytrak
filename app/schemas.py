from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from .constants import CALIBRATION_MODES, MANUAL_EVENT_KINDS


class LocalVideoIn(BaseModel):
    path: str
    title: str | None = None
    opponent: str = ""
    played_on: str = ""
    whistle_mode: str = "with"

    @field_validator("whistle_mode")
    @classmethod
    def validate_whistle_mode(cls, mode: str) -> str:
        if mode not in {"with", "without"}:
            raise ValueError("modo de apito inválido")
        return mode


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
    detail: str = ""
    note: str = ""

    @field_validator("detail")
    @classmethod
    def validate_detail(cls, detail: str) -> str:
        if detail not in {"", "start_late", "end_early", "both"}:
            raise ValueError("detalhe de exclusão inválido")
        return detail

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


class ManualClipIn(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end <= self.start:
            raise ValueError("o fim do clipe deve ser maior que o início")
        duration = self.end - self.start
        if duration < 1.0:
            raise ValueError("o clipe manual precisa ter pelo menos 1 segundo")
        if duration > 180.0:
            raise ValueError("o clipe manual é limitado a 3 minutos")
        return self


class ClipEditIn(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    save: bool = True

    @model_validator(mode="after")
    def validate_range(self):
        if self.end <= self.start:
            raise ValueError("o fim do clipe deve ser maior que o início")
        duration = self.end - self.start
        if duration < 1.0:
            raise ValueError("o clipe precisa ter pelo menos 1 segundo")
        if duration > 180.0:
            raise ValueError("o clipe é limitado a 3 minutos")
        return self


class ClipStarIn(BaseModel):
    starred: bool = True


class ClipStatusIn(BaseModel):
    status: str
    point_type: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, status: str) -> str:
        if status not in {"new", "saved"}:
            raise ValueError("status deve ser new ou saved")
        return status

    @field_validator("point_type")
    @classmethod
    def validate_point_type(cls, point_type: str | None) -> str | None:
        if point_type is not None and point_type not in {"rally", "serve"}:
            raise ValueError("point_type deve ser rally ou serve")
        return point_type


class SettingsIn(BaseModel):
    clip_output_dir: str = Field(default="", max_length=500)


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
