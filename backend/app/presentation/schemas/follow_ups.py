from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.presentation.schemas.trajectory import EvidenceItemOut, TrajectoryChangeOut

_FollowUpStatusLiteral = Literal[
    "EM_OBSERVACAO", "ACOMPANHAMENTO_ATIVO", "AGUARDANDO_RETORNO", "ENCERRADO"
]


class OpenFollowUpRequest(BaseModel):
    student_id: uuid.UUID
    trajectory_change_id: uuid.UUID


class FollowUpOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    status: _FollowUpStatusLiteral
    created_at: datetime


class RegisterFollowUpActionRequest(BaseModel):
    # `strip_whitespace=True` + `min_length=1` rejects blank/whitespace-only
    # text with FastAPI's standard 422 (spec I/O Matrix, "Blank action
    # text") — same idiom as `PedagogicalObservationCreateRequest.text`.
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class FollowUpActionOut(BaseModel):
    id: uuid.UUID
    follow_up_id: uuid.UUID
    description: str
    author_user_id: uuid.UUID
    created_at: datetime


class TrajectoryChangeEvidenceGroupOut(BaseModel):
    """One linked `TrajectoryChange` plus its own resolved evidence — Story
    4.3 groups `GET /follow-ups/{id}`'s evidence this way instead of a single
    flat list so the UI can render one collapsible section per change,
    ordered by `detected_at` (spec Boundaries & Constraints, RF-14/RF-20)."""

    trajectory_change: TrajectoryChangeOut
    evidence: list[EvidenceItemOut]


class FollowUpDetailOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    status: _FollowUpStatusLiteral
    created_at: datetime
    actions: list[FollowUpActionOut]
    trajectory_changes: list[TrajectoryChangeEvidenceGroupOut]


class ChangeFollowUpStatusRequest(BaseModel):
    status: _FollowUpStatusLiteral
