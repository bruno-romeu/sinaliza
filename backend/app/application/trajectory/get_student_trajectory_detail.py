"""`GetStudentTrajectoryDetailService` — the application-layer entry point for
`GET /students/{id}/trajectory/detail` (Story 3.4).

This service never forks `GetStudentTrajectoryService`'s convergence logic
(spec Boundaries & Constraints): it calls `GetStudentTrajectoryService.execute()`
once for the current snapshot/`trajectory_change`/`concerning_factor` — which
also performs the `StudentNotFoundError` check, so this service never
duplicates it — and layers three new reads on top:

1. **Series** — the charted indicator's value for each of the last ≤4
   `AcademicPeriod`s (by `start_date`), computed by calling the same pure
   `domain/trajectory.compute_trajectory_indicators` once per period with
   `as_of_date=min(period.end_date, as_of())` (mirrors `get_student_trajectory.py`'s
   window math, just anchored at a different "now" per period) — this service
   itself never computes a rate/average/count, only extracts the one field the
   chart needs from each period's `TrajectoryIndicators`. Concluded periods
   (`end_date <= as_of()`) anchor on their own `end_date`, a fixed historical
   point; the still-open current period anchors on the real clock instead,
   never a future date — otherwise its rolling window would reach past
   `as_of()` into dates with no data recorded yet, producing a skewed-or-`None`
   value for the chart's most relevant point on every mid-period view
   (code review finding, Story 3.4).
2. **Evidence** — real `TrajectoryChangeSource` rows for the current
   `trajectory_change` (if any), batch-resolved per `source_type` into
   factual PT-BR descriptions (RNF-11: never a free-text-only "AI flagged
   this").
3. **Observations** — the most recent 10 `PedagogicalObservation`s in the
   trailing 365 days, desc by date, for the page's timeline section.
4. **Student and open follow-up** (spec-ui-1) — the student's name and
   classroom for the page title, and the id of the requesting user's open
   (non-`ENCERRADO`) `FollowUp` for this student, so the page can offer
   "Ver acompanhamento" instead of opening a duplicate.

`chart_indicator` is chosen deterministically from `trajectory_change.type`
(spec Boundaries & Constraints table); absent a change, `attendance_rate` is
the default. `habitual_range` is the min/max of the series' own non-null
values — the student's own history only, never the classroom's — and is
`None` with fewer than 2 non-null points, never a fabricated range.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from app.application.trajectory.evidence import EvidenceItem, resolve_evidence
from app.application.trajectory.get_student_trajectory import (
    ConcerningFactor,
    GetStudentTrajectoryService,
)
from app.application.trajectory.ports import (
    AcademicPeriodRepositoryPort,
    AssignmentRepositoryPort,
    AssignmentSubmissionRepositoryPort,
    AttendanceRepositoryPort,
    GradeRepositoryPort,
    OpenFollowUpLookupPort,
    PedagogicalObservationRepositoryPort,
    StudentProfileRepositoryPort,
    TrajectoryChangeSourceRepositoryPort,
)
from app.domain.academic_period import AcademicPeriod
from app.domain.as_of import as_of
from app.domain.student import StudentProfile
from app.domain.trajectory import TrajectoryIndicators, compute_trajectory_indicators
from app.domain.trajectory_change import TrajectoryChange, TrajectoryChangeType

ChartIndicator = Literal["attendance_rate", "grade_average", "missing_assignments_count"]

_MAX_PERIODS_IN_SERIES = 4
_OBSERVATIONS_WINDOW_DAYS = 365
_MAX_OBSERVATIONS = 10
_DEFAULT_CHART_INDICATOR: ChartIndicator = "attendance_rate"

# spec Boundaries & Constraints: "the charted indicator is chosen
# deterministically from the trajectory_change's type".
_CHART_INDICATOR_BY_CHANGE_TYPE: dict[TrajectoryChangeType, ChartIndicator] = {
    TrajectoryChangeType.ATTENDANCE_DROP: "attendance_rate",
    TrajectoryChangeType.GRADE_DROP: "grade_average",
    TrajectoryChangeType.MISSING_ASSIGNMENTS_INCREASE: "missing_assignments_count",
    TrajectoryChangeType.COMBINED_DETERIORATION: "attendance_rate",
}


@dataclass(frozen=True)
class SeriesPoint:
    period_id: uuid.UUID
    period_label: str
    value: Decimal | None


@dataclass(frozen=True)
class HabitualRange:
    low: Decimal
    high: Decimal


@dataclass(frozen=True)
class ObservationItem:
    date: date
    text: str


@dataclass(frozen=True)
class TrajectoryDetailResult:
    chart_indicator: ChartIndicator
    series: list[SeriesPoint]
    habitual_range: HabitualRange | None
    trajectory_change: TrajectoryChange | None
    evidence: list[EvidenceItem]
    concerning_factor: ConcerningFactor | None
    observations: list[ObservationItem]
    student: StudentProfile | None = None
    open_follow_up_id: uuid.UUID | None = None


class GetStudentTrajectoryDetailService:
    def __init__(
        self,
        trajectory_service: GetStudentTrajectoryService,
        attendance_repository: AttendanceRepositoryPort,
        grade_repository: GradeRepositoryPort,
        assignment_repository: AssignmentRepositoryPort,
        assignment_submission_repository: AssignmentSubmissionRepositoryPort,
        academic_period_repository: AcademicPeriodRepositoryPort,
        pedagogical_observation_repository: PedagogicalObservationRepositoryPort,
        trajectory_change_source_repository: TrajectoryChangeSourceRepositoryPort,
        student_profile_repository: StudentProfileRepositoryPort | None = None,
        follow_up_repository: OpenFollowUpLookupPort | None = None,
    ) -> None:
        self._trajectory_service = trajectory_service
        self._attendance_repository = attendance_repository
        self._grade_repository = grade_repository
        self._assignment_repository = assignment_repository
        self._assignment_submission_repository = assignment_submission_repository
        self._academic_period_repository = academic_period_repository
        self._pedagogical_observation_repository = pedagogical_observation_repository
        self._trajectory_change_source_repository = trajectory_change_source_repository
        self._student_profile_repository = student_profile_repository
        self._follow_up_repository = follow_up_repository

    def execute(
        self, student_id: uuid.UUID, window_days: int, requesting_user_id: uuid.UUID
    ) -> TrajectoryDetailResult:
        # Raises StudentNotFoundError when applicable — never duplicated here.
        result = self._trajectory_service.execute(student_id, window_days)

        chart_indicator = self._chart_indicator_for(result.trajectory_change)

        periods = self._academic_period_repository.list_all()
        recent_periods = sorted(periods, key=lambda period: period.start_date)[
            -_MAX_PERIODS_IN_SERIES:
        ]
        series = [
            self._series_point(student_id, period, window_days, chart_indicator)
            for period in recent_periods
        ]
        habitual_range = self._habitual_range(series)

        evidence = self._resolve_evidence(result.trajectory_change, requesting_user_id)
        observations = self._recent_observations(student_id, requesting_user_id)

        student = (
            self._student_profile_repository.get_profile(student_id)
            if self._student_profile_repository is not None
            else None
        )
        open_follow_up = (
            self._follow_up_repository.find_open_for_student(student_id, requesting_user_id)
            if self._follow_up_repository is not None
            else None
        )

        return TrajectoryDetailResult(
            chart_indicator=chart_indicator,
            series=series,
            habitual_range=habitual_range,
            trajectory_change=result.trajectory_change,
            evidence=evidence,
            concerning_factor=result.concerning_factor,
            observations=observations,
            student=student,
            open_follow_up_id=open_follow_up.id if open_follow_up is not None else None,
        )

    @staticmethod
    def _chart_indicator_for(trajectory_change: TrajectoryChange | None) -> ChartIndicator:
        if trajectory_change is None:
            return _DEFAULT_CHART_INDICATOR
        return _CHART_INDICATOR_BY_CHANGE_TYPE[trajectory_change.type]

    def _series_point(
        self,
        student_id: uuid.UUID,
        period: AcademicPeriod,
        window_days: int,
        chart_indicator: ChartIndicator,
    ) -> SeriesPoint:
        # Concluded periods anchor on their own end_date (a fixed historical
        # point); the still-open current period anchors on the real clock
        # instead — never a future date, or its rolling window would reach
        # into dates with no data recorded yet (code review finding, Story 3.4).
        point_as_of = min(period.end_date, as_of())
        range_start = point_as_of - timedelta(days=2 * window_days)

        attendance_records = self._attendance_repository.list_by_student_in_range(
            student_id, range_start, point_as_of
        )
        assignments = self._assignment_repository.list_due_in_range_for_student(
            student_id, range_start, point_as_of
        )
        assignment_ids = [assignment.id for assignment in assignments]
        assignment_submissions = (
            self._assignment_submission_repository.list_by_student_and_assignments(
                student_id, assignment_ids
            )
            if assignment_ids
            else []
        )
        current_period_grades = self._grade_repository.list_by_student_and_periods(
            student_id, [period.id]
        )

        indicators = compute_trajectory_indicators(
            as_of_date=point_as_of,
            window_days=window_days,
            attendance_records=attendance_records,
            assignments=assignments,
            assignment_submissions=assignment_submissions,
            current_period_grades=current_period_grades,
            # previous_period_grades is always [] here: this per-period series
            # point only ever reads `indicators.grade_average` (current-period
            # grades), never `grade_trend` — harmless today, but a future field
            # that reads grade_trend from a series point would silently be
            # wrong (code review finding, Story 3.4).
            previous_period_grades=[],
        )

        return SeriesPoint(
            period_id=period.id,
            period_label=period.label,
            value=self._extract_indicator_value(indicators, chart_indicator),
        )

    @staticmethod
    def _extract_indicator_value(
        indicators: TrajectoryIndicators, chart_indicator: ChartIndicator
    ) -> Decimal | None:
        if chart_indicator == "attendance_rate":
            return indicators.attendance_rate
        if chart_indicator == "grade_average":
            return indicators.grade_average
        return Decimal(indicators.missing_assignments_count)

    @staticmethod
    def _habitual_range(series: list[SeriesPoint]) -> HabitualRange | None:
        values = [point.value for point in series if point.value is not None]
        if len(values) < 2:
            return None
        return HabitualRange(low=min(values), high=max(values))

    def _resolve_evidence(
        self, trajectory_change: TrajectoryChange | None, requesting_user_id: uuid.UUID
    ) -> list[EvidenceItem]:
        if trajectory_change is None:
            return []

        return resolve_evidence(
            trajectory_change.id,
            source_repo=self._trajectory_change_source_repository,
            attendance_repo=self._attendance_repository,
            grade_repo=self._grade_repository,
            submission_repo=self._assignment_submission_repository,
            observation_repo=self._pedagogical_observation_repository,
            requesting_user_id=requesting_user_id,
        )

    def _recent_observations(
        self, student_id: uuid.UUID, requesting_user_id: uuid.UUID
    ) -> list[ObservationItem]:
        as_of_date = as_of()
        start = as_of_date - timedelta(days=_OBSERVATIONS_WINDOW_DAYS)
        observations = self._pedagogical_observation_repository.list_by_student_in_range(
            student_id, start, as_of_date
        )
        ordered = sorted(observations, key=lambda observation: observation.created_at, reverse=True)
        most_recent = ordered[:_MAX_OBSERVATIONS]

        # RF-22/AD-8: the timeline must redact an observation's text exactly
        # like the evidence card does — re-resolve through get_by_ids, the
        # one place the restricted/visible rule lives, instead of using the
        # raw text list_by_student_in_range returns.
        redacted_by_id = {
            observation.id: observation
            for observation in self._pedagogical_observation_repository.get_by_ids(
                [observation.id for observation in most_recent], requesting_user_id
            )
        }
        return [
            ObservationItem(
                date=observation.created_at.date(),
                text=redacted_by_id[observation.id].text,
            )
            for observation in most_recent
        ]
