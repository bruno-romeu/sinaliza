from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.presentation.schemas.free_text import FreeText


class PedagogicalObservationCreateRequest(BaseModel):
    # Typed as `uuid.UUID` (not `str`) so a malformed id fails FastAPI's
    # standard 422 validation, never reaches the application service —
    # mirrors `AttendanceCreateRequest`/`GradeCreateRequest`'s precedent.
    student_id: uuid.UUID
    # Validation-only: run through the same enrollment gate as
    # attendance/grades/assignments, then discarded — never persisted on
    # `PedagogicalObservation` (spec Design Notes).
    classroom_id: uuid.UUID
    # `strip_whitespace=True` + `min_length=1` rejects blank/whitespace-only
    # text with FastAPI's standard 422 (spec I/O Matrix, "Whitespace-only
    # text (API bypass)") — never a bespoke `AppError`. `FreeText` carries
    # esse par e mais a recusa do byte NUL (`schemas/free_text.py`).
    text: FreeText
    # spec-ui-3: optional, so existing clients keep working. Only a
    # concern-marked observation counts as a convergence signal.
    registers_concern: bool = False


class PedagogicalObservationOut(BaseModel):
    id: str
    student_id: str
    author_user_id: str
    text: str
    created_at: datetime
    registers_concern: bool = False
