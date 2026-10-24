"""Convergence rule (RF-11) — pure Python, zero framework/I-O imports (AD-2,
AD-12): "Given ≥2 independent signals confirm in the same `period_id`, a
`TrajectoryChange` exists; given exactly 1, only a `concerning_factor` is
returned, never persisted."

Each `evaluate_*_signal` function is a pure, free function that evaluates one
signal and returns a `Signal` — there is no shared `SignalEvaluator`
type/protocol in the code; the four functions take different arguments
(attendance/grade take current+previous records, assignments additionally
takes a submissions map, pedagogical takes just the observations) and are
called individually by the application layer. The caller (`application/
trajectory/get_student_trajectory.py`, the only layer that does I/O) is
responsible for fetching the current/previous `AcademicPeriod`-scoped facts
(spec Boundaries & Constraints: by `period_id`, never `window_days`) and
passing them in here. Grade/attendance math reuses `domain/trajectory.py`'s
already-accepted `_attendance_rate`/`_grade_average` helpers verbatim — this
module never reimplements that arithmetic (spec Code Map).

**Limiares de confirmação** (spec Design Notes, `[ASSUMPTION]` of PRD RF-11,
fixed here for the MVP, calibration deferred):
- `ATTENDANCE`: `attendance_rate < 0.75` OR `attendance_trend <= -0.10`.
  (0.75 is the legal minimum attendance, so it stays an absolute floor.)
- `GRADE` (spec-ui-3, against the student's own history): the current
  período's average is at least 1.0 below the *lowest* average of the
  student's earlier períodos. A student who has always had low grades never
  confirms; without an earlier período there is nothing to compare to.
- `ASSIGNMENTS` (spec-ui-3, against the student's own history): the current
  período's missing count is at least 2 above the *highest* count of the
  student's earlier períodos, counting only `Assignment`s with ≥1
  `AssignmentSubmission` actually `NOT_DELIVERED`/`PARTIAL` recorded — never
  the ones with zero submissions registered, because every confirmed signal
  must be citable as a real `TrajectoryChangeSource` row (RNF-11), and
  `AssignmentSubmission` is never auto-created (Story 1.4). This is a
  deliberately stricter cut than 3.1's `missing_assignments_count` (which also
  counts total absence of any submission) — citability, not window math.
- `PEDAGOGICAL_OBSERVATION` (spec-ui-3): confirms iff ≥1
  `PedagogicalObservation` inside `[period.start_date, period.end_date]` was
  marked `registers_concern`. Neutral observations never confirm; the caller
  still cites them as evidence when a change is detected.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Sequence

from app.domain.assignment import Assignment
from app.domain.assignment_submission import AssignmentSubmission, AssignmentSubmissionStatus
from app.domain.attendance import AttendanceRecord, AttendanceStatus
from app.domain.grade import Grade
from app.domain.pedagogical_observation import PedagogicalObservation
from app.domain.trajectory import _attendance_rate, _grade_average
from app.domain.trajectory_change import SourceType, TrajectoryChangeType

_ATTENDANCE_RATE_THRESHOLD = Decimal("0.75")
_ATTENDANCE_TREND_THRESHOLD = Decimal("-0.10")
# spec-ui-3: grades and assignments compare against the student's own earlier
# períodos, never against a fixed cut shared by every student.
_GRADE_DROP_BELOW_HABITUAL = Decimal("1.0")
_MISSING_ABOVE_HABITUAL = 2
_CITABLE_MISSING_STATUSES = (
    AssignmentSubmissionStatus.NOT_DELIVERED,
    AssignmentSubmissionStatus.PARTIAL,
)


class SignalKind(str, Enum):
    ATTENDANCE = "ATTENDANCE"
    GRADE = "GRADE"
    ASSIGNMENTS = "ASSIGNMENTS"
    PEDAGOGICAL_OBSERVATION = "PEDAGOGICAL_OBSERVATION"


# The source_type a confirmed Signal of this kind is cited under.
SOURCE_TYPE_BY_SIGNAL_KIND: dict[SignalKind, SourceType] = {
    SignalKind.ATTENDANCE: SourceType.ATTENDANCE_RECORD,
    SignalKind.GRADE: SourceType.GRADE,
    SignalKind.ASSIGNMENTS: SourceType.ASSIGNMENT_SUBMISSION,
    SignalKind.PEDAGOGICAL_OBSERVATION: SourceType.PEDAGOGICAL_OBSERVATION,
}

# PT-BR factual phrase per kind (Voice and Tone, epic-3-context.md) — never
# diagnostic/predictive language.
_DESCRIPTION_PHRASE_BY_KIND: dict[SignalKind, str] = {
    SignalKind.ATTENDANCE: "queda de frequência",
    SignalKind.GRADE: "queda de notas",
    SignalKind.ASSIGNMENTS: "aumento de atividades pendentes",
    SignalKind.PEDAGOGICAL_OBSERVATION: "preocupação registrada pela equipe",
}

# Fixed, deterministic ordering for `build_description`'s phrase list —
# independent of set iteration order, so the same confirmed kinds always
# render the same sentence (RNF-09).
_DESCRIPTION_ORDER: tuple[SignalKind, ...] = (
    SignalKind.ATTENDANCE,
    SignalKind.GRADE,
    SignalKind.ASSIGNMENTS,
    SignalKind.PEDAGOGICAL_OBSERVATION,
)

_CORE_KINDS = frozenset(
    {SignalKind.ATTENDANCE, SignalKind.GRADE, SignalKind.ASSIGNMENTS}
)

_CHANGE_TYPE_BY_CORE_KIND: dict[SignalKind, TrajectoryChangeType] = {
    SignalKind.ATTENDANCE: TrajectoryChangeType.ATTENDANCE_DROP,
    SignalKind.GRADE: TrajectoryChangeType.GRADE_DROP,
    SignalKind.ASSIGNMENTS: TrajectoryChangeType.MISSING_ASSIGNMENTS_INCREASE,
}


@dataclass(frozen=True)
class Signal:
    confirmed: bool
    kind: SignalKind
    source_ids: tuple[uuid.UUID, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ConvergenceResult:
    """Either `change_type`/`confirmed_signals` are set (≥2 confirmed —
    caller upserts a `TrajectoryChange`) or `concerning_signal` is (exactly 1
    confirmed — caller returns an ephemeral `concerning_factor`), never both
    (spec I/O Matrix)."""

    change_type: TrajectoryChangeType | None = None
    confirmed_signals: tuple[Signal, ...] = field(default_factory=tuple)
    concerning_signal: Signal | None = None


def evaluate_attendance_signal(
    current_records: Sequence[AttendanceRecord],
    previous_records: Sequence[AttendanceRecord],
) -> Signal:
    current_rate = _attendance_rate(current_records)
    previous_rate = _attendance_rate(previous_records)
    trend = (
        current_rate - previous_rate
        if current_rate is not None and previous_rate is not None
        else None
    )
    confirmed = (current_rate is not None and current_rate < _ATTENDANCE_RATE_THRESHOLD) or (
        trend is not None and trend <= _ATTENDANCE_TREND_THRESHOLD
    )
    # spec-ui-3: cite only the absences. Days the student was present do not
    # support a "queda de frequência" reading and flooded the evidence card.
    source_ids = (
        tuple(record.id for record in current_records if record.status != AttendanceStatus.PRESENT)
        if confirmed
        else ()
    )
    return Signal(confirmed=confirmed, kind=SignalKind.ATTENDANCE, source_ids=source_ids)


def evaluate_grade_signal(
    current_grades: Sequence[Grade],
    earlier_period_grades: Sequence[Sequence[Grade]],
) -> Signal:
    """`earlier_period_grades` holds one list per earlier período (any order,
    empty lists ignored). Confirms when the current average sits at least
    `_GRADE_DROP_BELOW_HABITUAL` below the lowest earlier average."""
    current_average = _grade_average(current_grades)
    earlier_averages = [
        average
        for average in (_grade_average(grades) for grades in earlier_period_grades)
        if average is not None
    ]
    confirmed = (
        current_average is not None
        and bool(earlier_averages)
        and current_average <= min(earlier_averages) - _GRADE_DROP_BELOW_HABITUAL
    )
    source_ids = tuple(grade.id for grade in current_grades) if confirmed else ()
    return Signal(confirmed=confirmed, kind=SignalKind.GRADE, source_ids=source_ids)


def _citable_missing(
    assignments: Sequence[Assignment],
    submissions_by_assignment: dict[uuid.UUID, list[AssignmentSubmission]],
) -> tuple[int, list[uuid.UUID]]:
    """Counts assignments with ≥1 citable missing `AssignmentSubmission`
    (`NOT_DELIVERED`/`PARTIAL`) and collects every such submission's id —
    never counts an assignment with zero submissions registered (spec Design
    Notes: citability, not total-absence window math)."""
    count = 0
    source_ids: list[uuid.UUID] = []
    for assignment in assignments:
        submissions = submissions_by_assignment.get(assignment.id, [])
        missing = [s for s in submissions if s.status in _CITABLE_MISSING_STATUSES]
        if missing:
            count += 1
            source_ids.extend(submission.id for submission in missing)
    return count, source_ids


def evaluate_assignments_signal(
    current_assignments: Sequence[Assignment],
    earlier_period_assignments: Sequence[Sequence[Assignment]],
    submissions_by_assignment: dict[uuid.UUID, list[AssignmentSubmission]],
) -> Signal:
    """`earlier_period_assignments` holds one list per earlier período.
    Confirms when the current citable missing count is at least
    `_MISSING_ABOVE_HABITUAL` above the highest earlier count."""
    current_count, current_source_ids = _citable_missing(
        current_assignments, submissions_by_assignment
    )
    earlier_counts = [
        _citable_missing(assignments, submissions_by_assignment)[0]
        for assignments in earlier_period_assignments
    ]
    confirmed = bool(earlier_counts) and (
        current_count - max(earlier_counts) >= _MISSING_ABOVE_HABITUAL
    )
    source_ids = tuple(current_source_ids) if confirmed else ()
    return Signal(confirmed=confirmed, kind=SignalKind.ASSIGNMENTS, source_ids=source_ids)


def evaluate_pedagogical_signal(
    observations: Sequence[PedagogicalObservation],
) -> Signal:
    """spec-ui-3: only observations marked `registers_concern` confirm."""
    concerns = [observation for observation in observations if observation.registers_concern]
    confirmed = bool(concerns)
    source_ids = tuple(observation.id for observation in concerns)
    return Signal(
        confirmed=confirmed, kind=SignalKind.PEDAGOGICAL_OBSERVATION, source_ids=source_ids
    )


def decide_change_type(confirmed_kinds: frozenset[SignalKind]) -> TrajectoryChangeType:
    """Spec Design Notes' mapping table: ≥2 of `{ATTENDANCE, GRADE,
    ASSIGNMENTS}` confirmed → `COMBINED_DETERIORATION`; exactly 1 of those
    three (the other confirming signal is always `PEDAGOGICAL_OBSERVATION`,
    since `evaluate_convergence` only calls this with ≥2 confirmed kinds
    total) → that one's dedicated type."""
    confirmed_core = _CORE_KINDS & confirmed_kinds
    if len(confirmed_core) >= 2:
        return TrajectoryChangeType.COMBINED_DETERIORATION
    if len(confirmed_core) == 1:
        return _CHANGE_TYPE_BY_CORE_KIND[next(iter(confirmed_core))]
    raise ValueError(
        "decide_change_type requires >=2 confirmed signals with >=1 core "
        "(ATTENDANCE/GRADE/ASSIGNMENTS) signal among them"
    )


def _join_pt_br(phrases: Sequence[str]) -> str:
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + " e " + phrases[-1]


def _signals_in_period(confirmed_kinds: frozenset[SignalKind], period_label: str) -> str:
    ordered_phrases = [
        _DESCRIPTION_PHRASE_BY_KIND[kind] for kind in _DESCRIPTION_ORDER if kind in confirmed_kinds
    ]
    return f"{_join_pt_br(ordered_phrases)} no {period_label}"


def build_description(confirmed_kinds: frozenset[SignalKind], period_label: str) -> str:
    """"{Lista de sinais em PT-BR} no {period.label}", e.g. "Queda de
    frequência e queda de notas no 3º Bimestre" (spec Design Notes, Voice and
    Tone): always factual, never diagnostic/predictive language.

    spec-ui-1: no "Mudança recente:" prefix (every surface that shows this
    text already labels it as a change) and no dash before the period (the
    design system's voice rule forbids dashes in on-screen text)."""
    text = _signals_in_period(confirmed_kinds, period_label)
    return text[:1].upper() + text[1:]


def build_concerning_description(kind: SignalKind, period_label: str) -> str:
    """Text for a concerning factor, a single signal that has not converged
    into a change (spec-ui-1): "Sinal isolado: queda de notas no 3º
    Bimestre". Deliberately distinct from `build_description`, so an
    unconfirmed signal never reads like a detected change."""
    return f"Sinal isolado: {_signals_in_period(frozenset({kind}), period_label)}"


def evaluate_convergence(signals: Sequence[Signal]) -> ConvergenceResult:
    confirmed = [signal for signal in signals if signal.confirmed]
    if len(confirmed) >= 2:
        kinds = frozenset(signal.kind for signal in confirmed)
        return ConvergenceResult(
            change_type=decide_change_type(kinds), confirmed_signals=tuple(confirmed)
        )
    if len(confirmed) == 1:
        return ConvergenceResult(concerning_signal=confirmed[0])
    return ConvergenceResult()
