from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints


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
    # text (API bypass)") — never a bespoke `AppError`.
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PedagogicalObservationOut(BaseModel):
    id: str
    student_id: str
    author_user_id: str
    text: str
    created_at: datetime
