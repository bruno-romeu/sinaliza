"""`RegisterAssignmentService` — the one and only path that writes an
`Assignment` (spec Boundaries & Constraints: "assignment and submission
writes go through one application-service method each... never a router
assigning fields directly").

Checks the classroom exists first, then that the período exists — same order
and status codes as `RegisterGradeService`'s precedent (spec Boundaries &
Constraints, I/O Matrix). No duplicate-assignment rejection: `Assignment`
carries no UNIQUE constraint beyond FK integrity and no AC requires one
(spec Boundaries & Constraints).
"""

from __future__ import annotations

import uuid
from datetime import date

from app.application.academic_periods.ports import AcademicPeriodRepositoryPort
from app.application.assignments.errors import AcademicPeriodNotFoundError, ClassroomNotFoundError
from app.application.assignments.ports import AssignmentRepositoryPort
from app.application.attendance.ports import ClassroomRepositoryPort
from app.domain.assignment import Assignment


class RegisterAssignmentService:
    def __init__(
        self,
        classroom_repository: ClassroomRepositoryPort,
        academic_period_repository: AcademicPeriodRepositoryPort,
        assignment_repository: AssignmentRepositoryPort,
    ) -> None:
        self._classroom_repository = classroom_repository
        self._academic_period_repository = academic_period_repository
        self._assignment_repository = assignment_repository

    def execute(
        self,
        classroom_id: uuid.UUID,
        subject: str,
        period_id: uuid.UUID,
        due_date: date,
    ) -> Assignment:
        if self._classroom_repository.get_by_id(classroom_id) is None:
            raise ClassroomNotFoundError()

        if self._academic_period_repository.get_by_id(period_id) is None:
            raise AcademicPeriodNotFoundError()

        return self._assignment_repository.save(
            classroom_id=classroom_id,
            subject=subject,
            period_id=period_id,
            due_date=due_date,
        )
