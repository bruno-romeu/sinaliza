"""`RegisterAttendanceService` — the one and only path that writes an
`AttendanceRecord` (spec Boundaries & Constraints: "attendance writes go
through one application-service method... never a router assigning fields
directly").

Checks the classroom exists first (spec I/O Matrix, "Unknown classroom" —
same condition `ListEnrolledStudentsService` handles for `GET
/classrooms/{classroom_id}/students`), then that the student is actually
enrolled in it (spec I/O Matrix, "Student not enrolled"), then translates a
DB-level `UNIQUE(student_id, classroom_id, date)` violation into
`DuplicateAttendanceError` — the constraint is real at the database level
(AD-7, RNF-11), this is only a translation, not the source of truth.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.exc import IntegrityError

from app.application.attendance.errors import (
    ClassroomNotFoundError,
    DuplicateAttendanceError,
    StudentNotEnrolledError,
)
from app.application.attendance.ports import (
    AttendanceRepositoryPort,
    ClassroomRepositoryPort,
    StudentRepositoryPort,
)
from app.domain.attendance import AttendanceRecord, AttendanceStatus


class RegisterAttendanceService:
    def __init__(
        self,
        classroom_repository: ClassroomRepositoryPort,
        student_repository: StudentRepositoryPort,
        attendance_repository: AttendanceRepositoryPort,
    ) -> None:
        self._classroom_repository = classroom_repository
        self._student_repository = student_repository
        self._attendance_repository = attendance_repository

    def execute(
        self,
        student_id: uuid.UUID,
        classroom_id: uuid.UUID,
        date_: date,
        status: AttendanceStatus,
    ) -> AttendanceRecord:
        if self._classroom_repository.get_by_id(classroom_id) is None:
            raise ClassroomNotFoundError()

        if not self._student_repository.exists_enrollment(student_id, classroom_id):
            raise StudentNotEnrolledError()

        try:
            return self._attendance_repository.save(student_id, classroom_id, date_, status)
        except IntegrityError as exc:
            raise DuplicateAttendanceError() from exc
