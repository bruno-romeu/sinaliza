from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.presentation.schemas.free_text import ShortText
from app.presentation.schemas.school_dates import SchoolFactDate


class AcademicPeriodOut(BaseModel):
    id: str
    label: str
    start_date: date
    end_date: date
    order_index: int


class GradeCreateRequest(BaseModel):
    # Typed as `uuid.UUID` (not `str`) so a malformed id fails FastAPI's
    # standard 422 validation, never reaches the application service —
    # mirrors `AttendanceCreateRequest`'s precedent.
    student_id: uuid.UUID
    classroom_id: uuid.UUID
    # Bounds mirror `GradeModel.subject`'s `String(255)` column.
    # `strip_whitespace=True` runs before `min_length` is checked, so a
    # whitespace-only value (e.g. a single space) is rejected as empty
    # rather than persisted as a blank disciplina — matching
    # `AssignmentCreateRequest.subject` and
    # `PedagogicalObservationCreateRequest.text`. O byte NUL, que atravessava
    # esse par intacto, é recusado por `ShortText` (ver `schemas/free_text.py`).
    subject: ShortText
    period_id: uuid.UUID
    date: SchoolFactDate
    # `Field(ge=0, le=10)` is the API-boundary half of the double validation
    # (spec Boundaries & Constraints / Implementation Notes): a bypassed
    # request still gets FastAPI's untouched standard 422, never a bespoke
    # `AppError`. `max_digits=4, decimal_places=2` mirrors the DB column's
    # `Numeric(4,2)` shape.
    value: Annotated[Decimal, Field(ge=0, le=10, max_digits=4, decimal_places=2)]


class GradeOut(BaseModel):
    id: str
    student_id: str
    classroom_id: str
    subject: str
    period_id: str
    date: date
    value: Decimal
