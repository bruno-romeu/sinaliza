from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field


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
    subject: Annotated[str, Field(min_length=1, max_length=255)]
    period_id: uuid.UUID
    date: date
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
