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


class HomeOut(BaseModel):
    recent_changes: list[RecentChangeOut]


class StudentSearchResultOut(BaseModel):
    id: uuid.UUID
    name: str
    classroom_name: str


class StudentSearchOut(BaseModel):
    results: list[StudentSearchResultOut]
    count: int
