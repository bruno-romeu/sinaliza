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

**Story 3.2 — convergence detection (RF-11):** once the current `period_id`
is known, this service additionally evaluates the 4 `SignalEvaluator`s
(`domain/convergence.py`) over facts scoped to `[period.start_date,
period.end_date]` — the current and previous períodos by `order_index`,
never `window_days` (spec Boundaries & Constraints: this is a distinct read
from the rolling-window data used for the 6 indicators above, except for
`Grade`, which is already período-scoped and so is reused as-is). `evaluate_
convergence` then decides, purely, whether ≥2 signals confirm (upsert a
`TrajectoryChange` + its `TrajectoryChangeSource`s, same transaction, AD-1)
or exactly 1 does (ephemeral `ConcerningFactor`, never persisted) or none do.
No current period at all means no convergence evaluation is possible — both
`trajectory_change`/`concerning_factor` stay `None`, same as the indicators
already do in that case.

Each call is independent and stateless (no shared mutable state, no
in-process cache) — two concurrent requests for the same student simply run
this same sequence twice and get the same answer (spec I/O Matrix,
"Concorrência"): `as_of()` pins "now" for both, so `detected_at` is
deterministic (derived from `as_of()`, never wall-clock `datetime.now()`),
and the `ON CONFLICT` upsert resolves both writes to the same row without an
explicit lock."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from app.application.trajectory.errors import StudentNotFoundError
from app.application.trajectory.ports import (
    AcademicPeriodRepositoryPort,
    AssignmentRepositoryPort,
    AssignmentSubmissionRepositoryPort,
    AttendanceRepositoryPort,
    GradeRepositoryPort,
    PedagogicalObservationRepositoryPort,
    StudentRepositoryPort,
    TrajectoryChangeRepositoryPort,
)
from app.domain.academic_period import AcademicPeriod
from app.domain.as_of import as_of
from app.domain.convergence import (
    SOURCE_TYPE_BY_SIGNAL_KIND,
    SignalKind,
    build_concerning_description,
    build_description,
    evaluate_assignments_signal,
    evaluate_attendance_signal,
    evaluate_convergence,
    evaluate_grade_signal,
    evaluate_pedagogical_signal,
)
from app.domain.assignment_submission import AssignmentSubmission
from app.domain.grade import Grade
from app.domain.trajectory import TrajectoryIndicators, compute_trajectory_indicators
from app.domain.trajectory_change import TrajectoryChange, TrajectoryChangeSource


@dataclass(frozen=True)
class ConcerningFactor:
    kind: SignalKind
    description: str


@dataclass(frozen=True)
class TrajectoryResult:
    indicators: TrajectoryIndicators
    trajectory_change: TrajectoryChange | None
    concerning_factor: ConcerningFactor | None


class GetStudentTrajectoryService:
    def __init__(
        self,
        student_repository: StudentRepositoryPort,
        attendance_repository: AttendanceRepositoryPort,
        grade_repository: GradeRepositoryPort,
        assignment_repository: AssignmentRepositoryPort,
        assignment_submission_repository: AssignmentSubmissionRepositoryPort,
        academic_period_repository: AcademicPeriodRepositoryPort,
        pedagogical_observation_repository: PedagogicalObservationRepositoryPort,
        trajectory_change_repository: TrajectoryChangeRepositoryPort,
    ) -> None:
        self._student_repository = student_repository
        self._attendance_repository = attendance_repository
        self._grade_repository = grade_repository
        self._assignment_repository = assignment_repository
        self._assignment_submission_repository = assignment_submission_repository
        self._academic_period_repository = academic_period_repository
        self._pedagogical_observation_repository = pedagogical_observation_repository
        self._trajectory_change_repository = trajectory_change_repository

    def execute(self, student_id: uuid.UUID, window_days: int) -> TrajectoryResult:
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

        indicators = compute_trajectory_indicators(
            as_of_date=as_of_date,
            window_days=window_days,
            attendance_records=attendance_records,
            assignments=assignments,
            assignment_submissions=assignment_submissions,
            current_period_grades=current_period_grades,
            previous_period_grades=previous_period_grades,
        )

        trajectory_change = None
        concerning_factor = None
        if current_period is not None:
            trajectory_change, concerning_factor = self._evaluate_convergence(
                student_id=student_id,
                as_of_date=as_of_date,
                current_period=current_period,
                previous_period=previous_period,
                current_period_grades=current_period_grades,
                previous_period_grades=previous_period_grades,
            )

        return TrajectoryResult(
            indicators=indicators,
            trajectory_change=trajectory_change,
            concerning_factor=concerning_factor,
        )

    def _evaluate_convergence(
        self,
        *,
        student_id: uuid.UUID,
        as_of_date: date,
        current_period: AcademicPeriod,
        previous_period: AcademicPeriod | None,
        current_period_grades: list[Grade],
        previous_period_grades: list[Grade],
    ) -> tuple[TrajectoryChange | None, ConcerningFactor | None]:
        # Boundaries & Constraints: signal evaluation reads facts only within
        # [period.start_date, period.end_date] of the current/previous
        # período — a distinct read from the rolling-window data above.
        period_range_start = (
            previous_period.start_date if previous_period is not None else current_period.start_date
        )
        period_attendance_records = self._attendance_repository.list_by_student_in_range(
            student_id, period_range_start, current_period.end_date
        )
        current_period_attendance = [
            record
            for record in period_attendance_records
            if current_period.start_date <= record.date <= current_period.end_date
        ]
        previous_period_attendance = (
            [
                record
                for record in period_attendance_records
                if previous_period.start_date <= record.date <= previous_period.end_date
            ]
            if previous_period is not None
            else []
        )

        period_assignments = self._assignment_repository.list_due_in_range_for_student(
            student_id, period_range_start, current_period.end_date
        )
        current_period_assignments = [
            assignment
            for assignment in period_assignments
            if current_period.start_date <= assignment.due_date <= current_period.end_date
        ]
        previous_period_assignments = (
            [
                assignment
                for assignment in period_assignments
                if previous_period.start_date <= assignment.due_date <= previous_period.end_date
            ]
            if previous_period is not None
            else []
        )
        period_assignment_ids = [assignment.id for assignment in period_assignments]
        period_submissions = (
            self._assignment_submission_repository.list_by_student_and_assignments(
                student_id, period_assignment_ids
            )
            if period_assignment_ids
            else []
        )
        submissions_by_assignment: dict[uuid.UUID, list[AssignmentSubmission]] = {}
        for submission in period_submissions:
            submissions_by_assignment.setdefault(submission.assignment_id, []).append(submission)

        current_period_observations = (
            self._pedagogical_observation_repository.list_by_student_in_range(
                student_id, current_period.start_date, current_period.end_date
            )
        )

        signals = [
            evaluate_attendance_signal(current_period_attendance, previous_period_attendance),
            evaluate_grade_signal(current_period_grades, previous_period_grades),
            evaluate_assignments_signal(
                current_period_assignments, previous_period_assignments, submissions_by_assignment
            ),
            evaluate_pedagogical_signal(current_period_observations),
        ]

        result = evaluate_convergence(signals)

        if result.change_type is not None:
            change_id = uuid.uuid4()
            kinds = frozenset(signal.kind for signal in result.confirmed_signals)
            description = build_description(kinds, current_period.label)
            detected_at = datetime.combine(as_of_date, time.min, tzinfo=timezone.utc)
            change = TrajectoryChange(
                id=change_id,
                student_id=student_id,
                type=result.change_type,
                period_id=current_period.id,
                detected_at=detected_at,
                description=description,
            )
            sources = [
                TrajectoryChangeSource(
                    id=uuid.uuid4(),
                    trajectory_change_id=change_id,
                    source_type=SOURCE_TYPE_BY_SIGNAL_KIND[signal.kind],
                    source_id=source_id,
                )
                for signal in result.confirmed_signals
                for source_id in signal.source_ids
            ]
            persisted_change = self._trajectory_change_repository.upsert(change, sources)
            return persisted_change, None

        if result.concerning_signal is not None:
            description = build_concerning_description(
                result.concerning_signal.kind, current_period.label
            )
            return None, ConcerningFactor(kind=result.concerning_signal.kind, description=description)

        return None, None
