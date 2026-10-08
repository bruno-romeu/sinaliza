"""`GetStudentTrajectoryService` — the only application-layer entry point for
`GET /students/{id}/trajectory` (AD-1: computed synchronously, inside the
request, never by a job/cron).

Validates the student exists (and is `EVAL_DEMO`, via
`StudentRepositoryPort.get_by_id`'s built-in filter) before doing anything
else, raising `StudentNotFoundError` otherwise (spec I/O Matrix). It then
resolves `as_of()` once (AD-5) and the current/previous `AcademicPeriod` by
`order_index` (spec Boundaries & Constraints: "grade_average/trend segue
Grade.period_id... período vigente vs. anterior por order_index"), fetches
the raw facts each repository exposes, and delegates every bit of indicator
arithmetic to the pure `domain/trajectory.compute_trajectory_indicators`
(AD-12) — this service itself never computes a rate, average, or delta.

Each call is independent and stateless (no shared mutable state, no
in-process cache) — two concurrent requests for the same student simply run
this same sequence twice and get the same answer (spec I/O Matrix,
"Concorrência")."""

from __future__ import annotations

import uuid
from datetime import timedelta

from app.application.trajectory.errors import StudentNotFoundError
from app.application.trajectory.ports import (
    AcademicPeriodRepositoryPort,
    AssignmentRepositoryPort,
    AssignmentSubmissionRepositoryPort,
    AttendanceRepositoryPort,
    GradeRepositoryPort,
    StudentRepositoryPort,
)
from app.domain.as_of import as_of
from app.domain.trajectory import TrajectoryIndicators, compute_trajectory_indicators


class GetStudentTrajectoryService:
    def __init__(
        self,
        student_repository: StudentRepositoryPort,
        attendance_repository: AttendanceRepositoryPort,
        grade_repository: GradeRepositoryPort,
        assignment_repository: AssignmentRepositoryPort,
        assignment_submission_repository: AssignmentSubmissionRepositoryPort,
        academic_period_repository: AcademicPeriodRepositoryPort,
    ) -> None:
        self._student_repository = student_repository
        self._attendance_repository = attendance_repository
        self._grade_repository = grade_repository
        self._assignment_repository = assignment_repository
        self._assignment_submission_repository = assignment_submission_repository
        self._academic_period_repository = academic_period_repository

    def execute(self, student_id: uuid.UUID, window_days: int) -> TrajectoryIndicators:
        if self._student_repository.get_by_id(student_id) is None:
            raise StudentNotFoundError()

        as_of_date = as_of()
        range_start = as_of_date - timedelta(days=2 * window_days)

        periods = self._academic_period_repository.list_all()
        current_period = next(
            (period for period in periods if period.start_date <= as_of_date <= period.end_date),
            None,
        )
        previous_period = None
        if current_period is not None:
            previous_period = next(
                (
                    period
                    for period in periods
                    if period.order_index == current_period.order_index - 1
                ),
                None,
            )

        current_period_grades = (
            self._grade_repository.list_by_student_and_periods(student_id, [current_period.id])
            if current_period is not None
            else []
        )
        previous_period_grades = (
            self._grade_repository.list_by_student_and_periods(student_id, [previous_period.id])
            if previous_period is not None
            else []
        )

        attendance_records = self._attendance_repository.list_by_student_in_range(
            student_id, range_start, as_of_date
        )
        assignments = self._assignment_repository.list_due_in_range_for_student(
            student_id, range_start, as_of_date
        )
        assignment_ids = [assignment.id for assignment in assignments]
        assignment_submissions = (
            self._assignment_submission_repository.list_by_student_and_assignments(
                student_id, assignment_ids
            )
            if assignment_ids
            else []
        )

        return compute_trajectory_indicators(
            as_of_date=as_of_date,
            window_days=window_days,
            attendance_records=attendance_records,
            assignments=assignments,
            assignment_submissions=assignment_submissions,
            current_period_grades=current_period_grades,
            previous_period_grades=previous_period_grades,
        )
