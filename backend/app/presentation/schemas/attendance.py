from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.presentation.schemas.school_dates import SchoolFactDate


class ClassroomOut(BaseModel):
    id: str
    name: str
    academic_year: int


class StudentOut(BaseModel):
    id: str
    name: str


class AttendanceCreateRequest(BaseModel):
    # Typed as `uuid.UUID` (not `str`) so a malformed id fails FastAPI's
    # standard 422 validation, never reaches the application service.
    student_id: uuid.UUID
    classroom_id: uuid.UUID
    # Faixa e tipo estritos — ver `schemas/school_dates.py` para por que o
    # teto é `as_of()` e não uma constante.
    date: SchoolFactDate
    status: Literal["PRESENT", "ABSENT_JUSTIFIED", "ABSENT_UNJUSTIFIED"]


class AttendanceRecordOut(BaseModel):
    id: str
    student_id: str
    classroom_id: str
    date: date
    status: Literal["PRESENT", "ABSENT_JUSTIFIED", "ABSENT_UNJUSTIFIED"]
