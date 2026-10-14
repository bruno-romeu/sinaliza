from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.presentation.schemas.trajectory import EvidenceItemOut

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


class FollowUpDetailOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    status: _FollowUpStatusLiteral
    created_at: datetime
    evidence: list[EvidenceItemOut]
