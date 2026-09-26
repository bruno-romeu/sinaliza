"""Ports (interfaces) the `application/attendance` layer depends on.

`application/` only ever sees these Protocols — never a concrete class from
`infrastructure/` (AD-2). Concrete adapters are wired up in `composition.py`
(the composition root) and injected here.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Protocol

from app.domain.attendance import AttendanceRecord, AttendanceStatus
from app.domain.classroom import Classroom
from app.domain.student import Student


class ClassroomRepositoryPort(Protocol):
    def list_all(self) -> list[Classroom]: ...

    def get_by_id(self, classroom_id: uuid.UUID) -> Classroom | None: ...


class StudentRepositoryPort(Protocol):
    def list_enrolled(self, classroom_id: uuid.UUID) -> list[Student]: ...

    def exists_enrollment(self, student_id: uuid.UUID, classroom_id: uuid.UUID) -> bool: ...


class AttendanceRepositoryPort(Protocol):
    def save(
        self,
        student_id: uuid.UUID,
        classroom_id: uuid.UUID,
        date_: date,
        status: AttendanceStatus,
    ) -> AttendanceRecord: ...
