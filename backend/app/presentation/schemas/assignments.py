from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints


class AssignmentCreateRequest(BaseModel):
    # Typed as `uuid.UUID` (not `str`) so a malformed id fails FastAPI's
    # standard 422 validation, never reaches the application service —
    # mirrors `GradeCreateRequest`'s precedent.
    classroom_id: uuid.UUID
    # Bounds mirror `AssignmentModel.subject`'s `String(255)` column.
    # `strip_whitespace=True` runs before `min_length` is checked, so a
    # whitespace-only value (e.g. a single space) is rejected as empty
    # rather than persisted as a blank disciplina.
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    period_id: uuid.UUID
    due_date: date


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
    date: date


class AssignmentSubmissionOut(BaseModel):
    id: str
    assignment_id: str
    student_id: str
    status: Literal["DELIVERED", "NOT_DELIVERED", "PARTIAL"]
    date: date
