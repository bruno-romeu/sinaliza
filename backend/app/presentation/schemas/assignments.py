from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.presentation.schemas.free_text import ShortText
from app.presentation.schemas.school_dates import AssignmentDueDate, SchoolFactDate


class AssignmentCreateRequest(BaseModel):
    # Typed as `uuid.UUID` (not `str`) so a malformed id fails FastAPI's
    # standard 422 validation, never reaches the application service —
    # mirrors `GradeCreateRequest`'s precedent.
    classroom_id: uuid.UUID
    # Bounds mirror `AssignmentModel.subject`'s `String(255)` column.
    # `strip_whitespace=True` runs before `min_length` is checked, so a
    # whitespace-only value (e.g. a single space) is rejected as empty
    # rather than persisted as a blank disciplina.
    subject: ShortText
    period_id: uuid.UUID
    # A única data que pode estar à frente de `as_of()`: um prazo é, por
    # natureza, futuro. Ver `schemas/school_dates.py`.
    due_date: AssignmentDueDate


class AssignmentOut(BaseModel):
    id: str
    classroom_id: str
    subject: str
    period_id: str
    due_date: date


class AssignmentSubmissionCreateRequest(BaseModel):
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    status: Literal["DELIVERED", "NOT_DELIVERED", "PARTIAL"]
    date: SchoolFactDate


class AssignmentSubmissionOut(BaseModel):
    id: str
    assignment_id: str
    student_id: str
    status: Literal["DELIVERED", "NOT_DELIVERED", "PARTIAL"]
    date: date
