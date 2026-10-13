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
   `as_of_date=period.end_date` (mirrors `get_student_trajectory.py`'s window
   math, just anchored at a different "now" per period) — this service itself
   never computes a rate/average/count, only extracts the one field the chart
   needs from each period's `TrajectoryIndicators`.
2. **Evidence** — real `TrajectoryChangeSource` rows for the current
   `trajectory_change` (if any), batch-resolved per `source_type` into
   factual PT-BR descriptions (RNF-11: never a free-text-only "AI flagged
   this").
3. **Observations** — the most recent 10 `PedagogicalObservation`s in the
   trailing 365 days, desc by date, for the page's timeline section.

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
    PedagogicalObservationRepositoryPort,
    TrajectoryChangeSourceRepositoryPort,
)
from app.domain.academic_period import AcademicPeriod
from app.domain.assignment_submission import AssignmentSubmission, AssignmentSubmissionStatus
from app.domain.as_of import as_of
from app.domain.attendance import AttendanceRecord, AttendanceStatus
from app.domain.grade import Grade
from app.domain.pedagogical_observation import PedagogicalObservation
from app.domain.trajectory import TrajectoryIndicators, compute_trajectory_indicators
from app.domain.trajectory_change import SourceType, TrajectoryChange, TrajectoryChangeType

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

# Deterministic evidence ordering — mirrors `domain/convergence.py`'s
# `_DESCRIPTION_ORDER` so the same confirmed sources always render in the
# same order (RNF-09), independent of query/set iteration order.
_SOURCE_TYPE_ORDER: tuple[SourceType, ...] = (
    SourceType.ATTENDANCE_RECORD,
    SourceType.GRADE,
    SourceType.ASSIGNMENT_SUBMISSION,
    SourceType.PEDAGOGICAL_OBSERVATION,
)

_ATTENDANCE_STATUS_LABEL: dict[AttendanceStatus, str] = {
    AttendanceStatus.PRESENT: "Presença registrada",
    AttendanceStatus.ABSENT_JUSTIFIED: "Falta justificada",
    AttendanceStatus.ABSENT_UNJUSTIFIED: "Falta não justificada",
}

_SUBMISSION_STATUS_LABEL: dict[AssignmentSubmissionStatus, str] = {
    AssignmentSubmissionStatus.DELIVERED: "Atividade entregue",
    AssignmentSubmissionStatus.NOT_DELIVERED: "Atividade não entregue",
    AssignmentSubmissionStatus.PARTIAL: "Atividade entregue parcialmente",
}


def _format_date_br(value: date) -> str:
    return value.strftime("%d/%m/%Y")


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
class EvidenceItem:
    source_type: SourceType
    description: str
    date: date


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
    ) -> None:
        self._trajectory_service = trajectory_service
        self._attendance_repository = attendance_repository
        self._grade_repository = grade_repository
        self._assignment_repository = assignment_repository
        self._assignment_submission_repository = assignment_submission_repository
        self._academic_period_repository = academic_period_repository
        self._pedagogical_observation_repository = pedagogical_observation_repository
        self._trajectory_change_source_repository = trajectory_change_source_repository

    def execute(self, student_id: uuid.UUID, window_days: int) -> TrajectoryDetailResult:
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

        evidence = self._resolve_evidence(result.trajectory_change)
        observations = self._recent_observations(student_id)

        return TrajectoryDetailResult(
            chart_indicator=chart_indicator,
            series=series,
            habitual_range=habitual_range,
            trajectory_change=result.trajectory_change,
            evidence=evidence,
            concerning_factor=result.concerning_factor,
            observations=observations,
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
        range_start = period.end_date - timedelta(days=2 * window_days)

        attendance_records = self._attendance_repository.list_by_student_in_range(
            student_id, range_start, period.end_date
        )
        assignments = self._assignment_repository.list_due_in_range_for_student(
            student_id, range_start, period.end_date
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
            as_of_date=period.end_date,
            window_days=window_days,
            attendance_records=attendance_records,
            assignments=assignments,
            assignment_submissions=assignment_submissions,
            current_period_grades=current_period_grades,
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

    def _resolve_evidence(self, trajectory_change: TrajectoryChange | None) -> list[EvidenceItem]:
        if trajectory_change is None:
            return []

        sources = self._trajectory_change_source_repository.list_sources_by_change(
            trajectory_change.id
        )
        ids_by_type: dict[SourceType, list[uuid.UUID]] = {}
        for source in sources:
            ids_by_type.setdefault(source.source_type, []).append(source.source_id)

        items: list[EvidenceItem] = []
        for source_type in _SOURCE_TYPE_ORDER:
            ids = ids_by_type.get(source_type)
            if not ids:
                continue
            items.extend(self._resolve_items_for_type(source_type, ids))
        return items

    def _resolve_items_for_type(
        self, source_type: SourceType, ids: list[uuid.UUID]
    ) -> list[EvidenceItem]:
        if source_type == SourceType.ATTENDANCE_RECORD:
            records = self._attendance_repository.get_by_ids(ids)
            items = [
                EvidenceItem(
                    source_type=source_type,
                    description=self._attendance_description(record),
                    date=record.date,
                )
                for record in records
            ]
        elif source_type == SourceType.GRADE:
            grades = self._grade_repository.get_by_ids(ids)
            items = [
                EvidenceItem(
                    source_type=source_type,
                    description=self._grade_description(grade),
                    date=grade.date,
                )
                for grade in grades
            ]
        elif source_type == SourceType.ASSIGNMENT_SUBMISSION:
            submissions = self._assignment_submission_repository.get_by_ids(ids)
            items = [
                EvidenceItem(
                    source_type=source_type,
                    description=self._assignment_submission_description(submission),
                    date=submission.date,
                )
                for submission in submissions
            ]
        else:
            observations = self._pedagogical_observation_repository.get_by_ids(ids)
            items = [
                EvidenceItem(
                    source_type=source_type,
                    description=self._observation_description(observation),
                    date=observation.created_at.date(),
                )
                for observation in observations
            ]
        items.sort(key=lambda item: item.date)
        return items

    @staticmethod
    def _attendance_description(record: AttendanceRecord) -> str:
        return f"{_ATTENDANCE_STATUS_LABEL[record.status]} em {_format_date_br(record.date)}"

    @staticmethod
    def _grade_description(grade: Grade) -> str:
        return f"Nota {grade.value} em {grade.subject} — {_format_date_br(grade.date)}"

    @staticmethod
    def _assignment_submission_description(submission: AssignmentSubmission) -> str:
        return (
            f"{_SUBMISSION_STATUS_LABEL[submission.status]} em "
            f"{_format_date_br(submission.date)}"
        )

    @staticmethod
    def _observation_description(observation: PedagogicalObservation) -> str:
        return (
            f"Registro pedagógico em {_format_date_br(observation.created_at.date())}: "
            f"{observation.text}"
        )

    def _recent_observations(self, student_id: uuid.UUID) -> list[ObservationItem]:
        as_of_date = as_of()
        start = as_of_date - timedelta(days=_OBSERVATIONS_WINDOW_DAYS)
        observations = self._pedagogical_observation_repository.list_by_student_in_range(
            student_id, start, as_of_date
        )
        ordered = sorted(observations, key=lambda observation: observation.created_at, reverse=True)
        return [
            ObservationItem(date=observation.created_at.date(), text=observation.text)
            for observation in ordered[:_MAX_OBSERVATIONS]
        ]
