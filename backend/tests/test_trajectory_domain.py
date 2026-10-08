"""Unit tests for the pure `domain/trajectory.compute_trajectory_indicators`
(RNF-09: deterministic, no I/O) and `domain/as_of.as_of` (AD-5) — no DB, no
network, mirrors the "no DB" half of the spec's Code Map."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.domain.as_of import as_of
from app.domain.assignment import Assignment
from app.domain.assignment_submission import AssignmentSubmission, AssignmentSubmissionStatus
from app.domain.attendance import AttendanceRecord, AttendanceStatus
from app.domain.grade import Grade
from app.domain.trajectory import compute_trajectory_indicators

STUDENT_ID = uuid.uuid4()
CLASSROOM_ID = uuid.uuid4()
PERIOD_ID = uuid.uuid4()
PREVIOUS_PERIOD_ID = uuid.uuid4()
AS_OF_DATE = date(2026, 9, 24)
WINDOW_DAYS = 30


def _attendance(day: date, status: AttendanceStatus) -> AttendanceRecord:
    return AttendanceRecord(
        id=uuid.uuid4(), student_id=STUDENT_ID, classroom_id=CLASSROOM_ID, date=day, status=status
    )


def _grade(value: str, period_id: uuid.UUID = PERIOD_ID, day: date = AS_OF_DATE) -> Grade:
    return Grade(
        id=uuid.uuid4(),
        student_id=STUDENT_ID,
        classroom_id=CLASSROOM_ID,
        subject="Matemática",
        period_id=period_id,
        date=day,
        value=Decimal(value),
    )


def _assignment(due_date: date) -> Assignment:
    return Assignment(
        id=uuid.uuid4(), classroom_id=CLASSROOM_ID, subject="Matemática", period_id=PERIOD_ID, due_date=due_date
    )


def _submission(assignment_id: uuid.UUID, status: AssignmentSubmissionStatus, day: date) -> AssignmentSubmission:
    return AssignmentSubmission(
        id=uuid.uuid4(), assignment_id=assignment_id, student_id=STUDENT_ID, status=status, date=day
    )


# --- as_of() ------------------------------------------------------------------


def test_as_of_defaults_to_real_utc_today_without_override(monkeypatch) -> None:
    monkeypatch.delenv("SINALIZA_DEMO_AS_OF", raising=False)
    from datetime import datetime, timezone

    assert as_of() == datetime.now(timezone.utc).date()


def test_as_of_uses_env_override_when_set(monkeypatch) -> None:
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", "2026-09-24")
    assert as_of() == date(2026, 9, 24)


def test_as_of_reads_env_fresh_on_every_call(monkeypatch) -> None:
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", "2026-01-01")
    assert as_of() == date(2026, 1, 1)
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", "2026-12-31")
    assert as_of() == date(2026, 12, 31)


def test_as_of_raises_descriptive_error_on_malformed_override(monkeypatch) -> None:
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", "not-a-date")

    with pytest.raises(ValueError, match="SINALIZA_DEMO_AS_OF"):
        as_of()


# --- compute_trajectory_indicators: no data ------------------------------------


def test_compute_trajectory_indicators_with_no_data_returns_none_and_zero_counts() -> None:
    indicators = compute_trajectory_indicators(
        as_of_date=AS_OF_DATE,
        window_days=WINDOW_DAYS,
        attendance_records=[],
        assignments=[],
        assignment_submissions=[],
        current_period_grades=[],
        previous_period_grades=[],
    )

    assert indicators.attendance_rate is None
    assert indicators.attendance_trend is None
    assert indicators.grade_average is None
    assert indicators.grade_trend is None
    assert indicators.missing_assignments_count == 0
    assert indicators.missing_assignment_delta == 0


# --- compute_trajectory_indicators: happy path ---------------------------------


def test_compute_trajectory_indicators_happy_path() -> None:
    attendance_records = [
        # current window [2026-08-25, 2026-09-24]: 1 present, 1 absent -> 0.5
        _attendance(date(2026, 9, 20), AttendanceStatus.PRESENT),
        _attendance(date(2026, 9, 21), AttendanceStatus.ABSENT_UNJUSTIFIED),
        # previous window [2026-07-26, 2026-08-25): 1 present -> 1.0
        _attendance(date(2026, 8, 10), AttendanceStatus.PRESENT),
    ]
    current_period_grades = [_grade("8.00")]
    previous_period_grades = [_grade("6.00", period_id=PREVIOUS_PERIOD_ID, day=date(2026, 6, 15))]

    assignment_current = _assignment(due_date=date(2026, 9, 22))
    assignments = [assignment_current]
    assignment_submissions = [
        _submission(assignment_current.id, AssignmentSubmissionStatus.NOT_DELIVERED, date(2026, 9, 22))
    ]

    indicators = compute_trajectory_indicators(
        as_of_date=AS_OF_DATE,
        window_days=WINDOW_DAYS,
        attendance_records=attendance_records,
        assignments=assignments,
        assignment_submissions=assignment_submissions,
        current_period_grades=current_period_grades,
        previous_period_grades=previous_period_grades,
    )

    assert indicators.attendance_rate == Decimal("0.5")
    assert indicators.attendance_trend == Decimal("-0.5")
    assert indicators.grade_average == Decimal("8.00")
    assert indicators.grade_trend == Decimal("2.00")
    assert indicators.missing_assignments_count == 1
    assert indicators.missing_assignment_delta == 1  # 1 current - 0 previous


# --- "Pendente" matrix ---------------------------------------------------------


def test_missing_assignments_counts_absence_not_delivered_and_partial_but_not_delivered() -> None:
    no_submission = _assignment(due_date=date(2026, 9, 10))
    not_delivered = _assignment(due_date=date(2026, 9, 11))
    partial = _assignment(due_date=date(2026, 9, 12))
    delivered = _assignment(due_date=date(2026, 9, 13))

    assignments = [no_submission, not_delivered, partial, delivered]
    assignment_submissions = [
        _submission(not_delivered.id, AssignmentSubmissionStatus.NOT_DELIVERED, date(2026, 9, 11)),
        _submission(partial.id, AssignmentSubmissionStatus.PARTIAL, date(2026, 9, 12)),
        _submission(delivered.id, AssignmentSubmissionStatus.DELIVERED, date(2026, 9, 13)),
    ]

    indicators = compute_trajectory_indicators(
        as_of_date=AS_OF_DATE,
        window_days=WINDOW_DAYS,
        attendance_records=[],
        assignments=assignments,
        assignment_submissions=assignment_submissions,
        current_period_grades=[],
        previous_period_grades=[],
    )

    # no_submission, not_delivered, partial all count; delivered does not.
    assert indicators.missing_assignments_count == 3


# --- Determinism / purity -------------------------------------------------------


def test_compute_trajectory_indicators_is_deterministic_across_repeated_calls() -> None:
    attendance_records = [_attendance(date(2026, 9, 20), AttendanceStatus.PRESENT)]
    kwargs = dict(
        as_of_date=AS_OF_DATE,
        window_days=WINDOW_DAYS,
        attendance_records=attendance_records,
        assignments=[],
        assignment_submissions=[],
        current_period_grades=[_grade("7.50")],
        previous_period_grades=[],
    )

    first = compute_trajectory_indicators(**kwargs)
    second = compute_trajectory_indicators(**kwargs)

    assert first == second
