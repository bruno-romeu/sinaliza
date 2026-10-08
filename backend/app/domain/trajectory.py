"""Pure trajectory-indicator math (AD-12) — pure Python, zero framework/I-O
imports (AD-2), mirrors the style of `domain/attendance.py`/`domain/grade.py`.

`compute_trajectory_indicators` is the one and only place the six indicators
(`attendance_rate`, `attendance_trend`, `grade_average`, `grade_trend`,
`missing_assignments_count`, `missing_assignment_delta`) are calculated —
reused as-is by Epic 5's ML feature engineering (`epic-3-context.md`)
without reimplementing the formula.

**Rolling window vs. período (spec Boundaries & Constraints):**
`attendance_rate`/`trend` and `missing_assignments_count`/`delta` use a
rolling window of `window_days`, split into two equal, non-overlapping
halves: the *current* window `[as_of_date - window_days, as_of_date]`
(inclusive both ends) and the *previous* window
`[as_of_date - 2*window_days, as_of_date - window_days)` (inclusive start,
exclusive end — spec Design Notes' window=30 example). `grade_average`/
`trend` instead follow `Grade.period_id`: the caller (the application
service, which does I/O) resolves the current/previous `AcademicPeriod` and
passes in only the grades that belong to each; this function never sees an
`AcademicPeriod` at all.

**Trend/delta = atual − anterior, nunca regressão; `None` sem comparável**
(spec Boundaries & Constraints): `attendance_trend`/`grade_trend` are `None`
whenever either side of the subtraction has no data to average (division by
zero avoided structurally, never silently treated as `0`).
`missing_assignments_count` is always a plain count — `0` with no data — so
`missing_assignment_delta` is always computable as current − previous counts
and is never `None` (spec I/O Matrix: "missing_assignments_count=0" with no
comparable rows, not "count unknown").

**"Pendente" (spec Boundaries & Constraints):** an `Assignment` counts as
missing unless at least one of the student's `AssignmentSubmission`s for it
is `DELIVERED` — absence of any submission, `NOT_DELIVERED`, and `PARTIAL`
all count. Callers are expected to have already filtered `assignments` to
ones that are actually vencida relative to `as_of_date` (the repository
layer's `filter_as_of` on `due_date` does this); this function additionally
only considers an assignment "missing" if its `due_date` falls inside the
current or previous window it is asked to compute, so a stray out-of-window
row passed in by mistake is harmless.

Rates/averages are rounded to a fixed number of decimal places so the API
response is stable and comparable across requests (RNF-09 — "resultado
idêntico" under concurrent, independent recomputation): `attendance_rate`/
`attendance_trend` to 4 decimal places, `grade_average`/`grade_trend` to 2
(matching `GradeModel.value`'s `Numeric(4,2)` column scale).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence

from app.domain.assignment import Assignment
from app.domain.assignment_submission import AssignmentSubmission, AssignmentSubmissionStatus
from app.domain.attendance import AttendanceRecord, AttendanceStatus
from app.domain.grade import Grade

_ATTENDANCE_QUANT = Decimal("0.0001")
_GRADE_QUANT = Decimal("0.01")


@dataclass(frozen=True)
class TrajectoryIndicators:
    attendance_rate: Decimal | None
    attendance_trend: Decimal | None
    grade_average: Decimal | None
    grade_trend: Decimal | None
    missing_assignments_count: int
    missing_assignment_delta: int


def _attendance_rate(records: Sequence[AttendanceRecord]) -> Decimal | None:
    if not records:
        return None
    present = sum(1 for record in records if record.status == AttendanceStatus.PRESENT)
    rate = Decimal(present) / Decimal(len(records))
    return rate.quantize(_ATTENDANCE_QUANT, rounding=ROUND_HALF_UP)


def _grade_average(grades: Sequence[Grade]) -> Decimal | None:
    if not grades:
        return None
    total = sum((grade.value for grade in grades), Decimal(0))
    average = total / Decimal(len(grades))
    return average.quantize(_GRADE_QUANT, rounding=ROUND_HALF_UP)


def _missing_count(
    assignments: Sequence[Assignment],
    submissions_by_assignment: dict[uuid.UUID, list[AssignmentSubmission]],
) -> int:
    count = 0
    for assignment in assignments:
        submissions = submissions_by_assignment.get(assignment.id, ())
        delivered = any(
            submission.status == AssignmentSubmissionStatus.DELIVERED for submission in submissions
        )
        if not delivered:
            count += 1
    return count


def compute_trajectory_indicators(
    *,
    as_of_date: date,
    window_days: int,
    attendance_records: Sequence[AttendanceRecord],
    assignments: Sequence[Assignment],
    assignment_submissions: Sequence[AssignmentSubmission],
    current_period_grades: Sequence[Grade],
    previous_period_grades: Sequence[Grade],
) -> TrajectoryIndicators:
    """Pure — no I/O, no clock access (`as_of_date` is a parameter, never
    computed internally), deterministic for a given set of inputs (RNF-09:
    two concurrent, independent calls with the same inputs return an
    identical result)."""
    current_start = as_of_date - timedelta(days=window_days)
    previous_start = as_of_date - timedelta(days=2 * window_days)

    current_attendance = [
        record for record in attendance_records if current_start <= record.date <= as_of_date
    ]
    previous_attendance = [
        record for record in attendance_records if previous_start <= record.date < current_start
    ]

    attendance_rate = _attendance_rate(current_attendance)
    previous_attendance_rate = _attendance_rate(previous_attendance)
    attendance_trend = (
        attendance_rate - previous_attendance_rate
        if attendance_rate is not None and previous_attendance_rate is not None
        else None
    )

    grade_average = _grade_average(current_period_grades)
    previous_grade_average = _grade_average(previous_period_grades)
    grade_trend = (
        grade_average - previous_grade_average
        if grade_average is not None and previous_grade_average is not None
        else None
    )

    current_assignments = [
        assignment
        for assignment in assignments
        if current_start <= assignment.due_date <= as_of_date
    ]
    previous_assignments = [
        assignment
        for assignment in assignments
        if previous_start <= assignment.due_date < current_start
    ]

    submissions_by_assignment: dict[uuid.UUID, list[AssignmentSubmission]] = {}
    for submission in assignment_submissions:
        submissions_by_assignment.setdefault(submission.assignment_id, []).append(submission)

    missing_assignments_count = _missing_count(current_assignments, submissions_by_assignment)
    previous_missing_assignments_count = _missing_count(previous_assignments, submissions_by_assignment)
    missing_assignment_delta = missing_assignments_count - previous_missing_assignments_count

    return TrajectoryIndicators(
        attendance_rate=attendance_rate,
        attendance_trend=attendance_trend,
        grade_average=grade_average,
        grade_trend=grade_trend,
        missing_assignments_count=missing_assignments_count,
        missing_assignment_delta=missing_assignment_delta,
    )
