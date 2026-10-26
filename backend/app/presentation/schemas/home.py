from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RecentChangeOut(BaseModel):
    student_id: uuid.UUID
    student_name: str
    type: Literal[
        "ATTENDANCE_DROP",
        "GRADE_DROP",
        "MISSING_ASSIGNMENTS_INCREASE",
        "COMBINED_DETERIORATION",
    ]
    description: str
    detected_at: datetime


class InProgressFollowUpOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    status: Literal[
        "EM_OBSERVACAO",
        "ACOMPANHAMENTO_ATIVO",
        "AGUARDANDO_RETORNO",
        "ENCERRADO",
    ]


class HomeOut(BaseModel):
    recent_changes: list[RecentChangeOut]
    in_progress_follow_ups: list[InProgressFollowUpOut]
    in_progress_follow_ups_total: int
    in_progress_follow_ups_page: int
    in_progress_follow_ups_page_size: int


class StudentSearchResultOut(BaseModel):
    id: uuid.UUID
    name: str
    classroom_name: str


class StudentSearchOut(BaseModel):
    results: list[StudentSearchResultOut]
    count: int
    total: int
    page: int
    page_size: int
