"""`RegisterGradeService` — the one and only path that writes a `Grade`
(spec Boundaries & Constraints: "grade writes go through one
application-service method... never a router assigning fields directly").

Checks the classroom exists first, then that the student is actually
enrolled in it, then that the período exists — same order and status codes
as `RegisterAttendanceService`'s precedent (spec Boundaries & Constraints,
I/O Matrix). No duplicate-grade rejection: `Grade` carries no UNIQUE
constraint and no AC requires one (spec Boundaries & Constraints, Design
Notes) — a student may legitimately receive multiple assessments in the
same período.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.application.academic_periods.ports import AcademicPeriodRepositoryPort
from app.application.attendance.ports import ClassroomRepositoryPort, StudentRepositoryPort
from app.application.grades.errors import (
    AcademicPeriodNotFoundError,
    ClassroomNotFoundError,
    StudentNotEnrolledError,
)
from app.application.grades.ports import GradeRepositoryPort
from app.domain.grade import Grade


class RegisterGradeService:
    def __init__(
        self,
        classroom_repository: ClassroomRepositoryPort,
        student_repository: StudentRepositoryPort,
        academic_period_repository: AcademicPeriodRepositoryPort,
        grade_repository: GradeRepositoryPort,
    ) -> None:
        self._classroom_repository = classroom_repository
        self._student_repository = student_repository
        self._academic_period_repository = academic_period_repository
        self._grade_repository = grade_repository

    def execute(
        self,
        student_id: uuid.UUID,
        classroom_id: uuid.UUID,
        subject: str,
        period_id: uuid.UUID,
        date_: date,
        value: Decimal,
    ) -> Grade:
        if self._classroom_repository.get_by_id(classroom_id) is None:
            raise ClassroomNotFoundError()

        if not self._student_repository.exists_enrollment(student_id, classroom_id):
            raise StudentNotEnrolledError()

        if self._academic_period_repository.get_by_id(period_id) is None:
            raise AcademicPeriodNotFoundError()

        return self._grade_repository.save(
            student_id=student_id,
            classroom_id=classroom_id,
            subject=subject,
            period_id=period_id,
            date_=date_,
            value=value,
        )
