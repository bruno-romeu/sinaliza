"""Ports (interfaces) the `application/grades` layer depends on.

`ClassroomRepositoryPort`/`StudentRepositoryPort` are reused as-is from
`application/attendance/ports.py` (spec Code Map: "import only, no
changes") — only `GradeRepositoryPort` is new here.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.domain.grade import Grade


class GradeRepositoryPort(Protocol):
    def save(
        self,
        student_id: uuid.UUID,
        classroom_id: uuid.UUID,
        subject: str,
        period_id: uuid.UUID,
        date_: date,
        value: Decimal,
    ) -> Grade: ...
