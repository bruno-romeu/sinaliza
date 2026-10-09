"""Unit tests for the pure `domain/convergence.py` (RF-11, AD-12) — no DB, no
network. Covers all 4 `SignalEvaluator`s, `decide_change_type`'s mapping
table, `build_description`'s PT-BR text, and `evaluate_convergence`'s 3-way
branch (converged / single signal / none)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.domain.assignment import Assignment
from app.domain.assignment_submission import AssignmentSubmission, AssignmentSubmissionStatus
from app.domain.attendance import AttendanceRecord, AttendanceStatus
from app.domain.convergence import (
    Signal,
    SignalKind,
    build_description,
    decide_change_type,
    evaluate_assignments_signal,
    evaluate_attendance_signal,
    evaluate_convergence,
    evaluate_grade_signal,
    evaluate_pedagogical_signal,
)
from app.domain.grade import Grade
from app.domain.pedagogical_observation import PedagogicalObservation
from app.domain.trajectory_change import TrajectoryChangeType

STUDENT_ID = uuid.uuid4()
CLASSROOM_ID = uuid.uuid4()
PERIOD_ID = uuid.uuid4()
AUTHOR_ID = uuid.uuid4()


def _attendance(day: date, status: AttendanceStatus) -> AttendanceRecord:
    return AttendanceRecord(
        id=uuid.uuid4(), student_id=STUDENT_ID, classroom_id=CLASSROOM_ID, date=day, status=status
    )


def _grade(value: str, day: date = date(2026, 9, 1)) -> Grade:
    return Grade(
        id=uuid.uuid4(),
        student_id=STUDENT_ID,
        classroom_id=CLASSROOM_ID,
        subject="Matemática",
        period_id=PERIOD_ID,
        date=day,
        value=Decimal(value),
    )


def _assignment(due_date: date = date(2026, 9, 1)) -> Assignment:
    return Assignment(
        id=uuid.uuid4(), classroom_id=CLASSROOM_ID, subject="Matemática", period_id=PERIOD_ID, due_date=due_date
    )


def _submission(assignment_id: uuid.UUID, status: AssignmentSubmissionStatus) -> AssignmentSubmission:
    return AssignmentSubmission(
        id=uuid.uuid4(),
        assignment_id=assignment_id,
        student_id=STUDENT_ID,
        status=status,
        date=date(2026, 9, 1),
    )


def _observation(day: date = date(2026, 9, 1)) -> PedagogicalObservation:
    from datetime import datetime, timezone

    return PedagogicalObservation(
        id=uuid.uuid4(),
        student_id=STUDENT_ID,
        author_user_id=AUTHOR_ID,
        text="Observação de teste.",
        created_at=datetime(day.year, day.month, day.day, 12, 0, tzinfo=timezone.utc),
    )


# --- evaluate_attendance_signal -------------------------------------------------


def test_attendance_signal_confirms_when_rate_below_threshold() -> None:
    current = [_attendance(date(2026, 9, 1), AttendanceStatus.ABSENT_UNJUSTIFIED)] * 3 + [
        _attendance(date(2026, 9, 2), AttendanceStatus.PRESENT)
    ]
    signal = evaluate_attendance_signal(current, [])

    assert signal.confirmed is True
    assert signal.kind == SignalKind.ATTENDANCE
    assert len(signal.source_ids) == len(current)


def test_attendance_signal_confirms_when_trend_drops_enough() -> None:
    # current rate 0.8 (>= 0.75), but trend drop of 0.2 vs previous 1.0
    current = [_attendance(date(2026, 9, 1), AttendanceStatus.PRESENT)] * 4 + [
        _attendance(date(2026, 9, 2), AttendanceStatus.ABSENT_UNJUSTIFIED)
    ]
    previous = [_attendance(date(2026, 7, 1), AttendanceStatus.PRESENT)] * 2

    signal = evaluate_attendance_signal(current, previous)

    assert signal.confirmed is True


def test_attendance_signal_does_not_confirm_with_no_data() -> None:
    signal = evaluate_attendance_signal([], [])

    assert signal.confirmed is False
    assert signal.source_ids == ()


def test_attendance_signal_does_not_confirm_above_threshold_with_no_bad_trend() -> None:
    current = [_attendance(date(2026, 9, 1), AttendanceStatus.PRESENT)] * 4
    previous = [_attendance(date(2026, 7, 1), AttendanceStatus.PRESENT)] * 4

    signal = evaluate_attendance_signal(current, previous)

    assert signal.confirmed is False


# --- evaluate_grade_signal -------------------------------------------------------


def test_grade_signal_confirms_when_average_below_threshold() -> None:
    signal = evaluate_grade_signal([_grade("4.00")], [])

    assert signal.confirmed is True
    assert signal.kind == SignalKind.GRADE
    assert len(signal.source_ids) == 1


def test_grade_signal_confirms_when_trend_drops_enough() -> None:
    signal = evaluate_grade_signal([_grade("6.00")], [_grade("8.00")])

    assert signal.confirmed is True


def test_grade_signal_does_not_confirm_with_no_data() -> None:
    signal = evaluate_grade_signal([], [])

    assert signal.confirmed is False
    assert signal.source_ids == ()


def test_grade_signal_does_not_confirm_above_threshold_with_small_trend() -> None:
    signal = evaluate_grade_signal([_grade("7.00")], [_grade("7.50")])

    assert signal.confirmed is False


# --- evaluate_assignments_signal --------------------------------------------------


def test_assignments_signal_confirms_when_citable_missing_count_reaches_threshold() -> None:
    a1, a2 = _assignment(), _assignment()
    submissions_by_assignment = {
        a1.id: [_submission(a1.id, AssignmentSubmissionStatus.NOT_DELIVERED)],
        a2.id: [_submission(a2.id, AssignmentSubmissionStatus.PARTIAL)],
    }

    signal = evaluate_assignments_signal([a1, a2], [], submissions_by_assignment)

    assert signal.confirmed is True
    assert signal.kind == SignalKind.ASSIGNMENTS
    assert len(signal.source_ids) == 2


def test_assignments_signal_ignores_assignments_with_zero_submissions() -> None:
    """Design Notes: never counts an assignment with zero submissions
    registered — only ones with a real citable NOT_DELIVERED/PARTIAL row."""
    a1, a2 = _assignment(), _assignment()
    # a1 has no submission at all; a2 has a DELIVERED one (not missing).
    submissions_by_assignment = {a2.id: [_submission(a2.id, AssignmentSubmissionStatus.DELIVERED)]}

    signal = evaluate_assignments_signal([a1, a2], [], submissions_by_assignment)

    assert signal.confirmed is False
    assert signal.source_ids == ()


def test_assignments_signal_confirms_on_delta_even_below_count_threshold() -> None:
    a1 = _assignment()
    current = [a1]
    previous: list[Assignment] = []
    submissions_by_assignment = {a1.id: [_submission(a1.id, AssignmentSubmissionStatus.NOT_DELIVERED)]}

    # current count=1 (< 2), previous count=0 => delta=1 (< 2) => not confirmed
    signal = evaluate_assignments_signal(current, previous, submissions_by_assignment)
    assert signal.confirmed is False

    # Bump current count to 2 via a second missing assignment => delta=2 => confirmed
    a2 = _assignment()
    submissions_by_assignment[a2.id] = [_submission(a2.id, AssignmentSubmissionStatus.PARTIAL)]
    signal = evaluate_assignments_signal([a1, a2], previous, submissions_by_assignment)
    assert signal.confirmed is True


# --- evaluate_pedagogical_signal --------------------------------------------------


def test_pedagogical_signal_confirms_with_at_least_one_observation() -> None:
    signal = evaluate_pedagogical_signal([_observation()])

    assert signal.confirmed is True
    assert signal.kind == SignalKind.PEDAGOGICAL_OBSERVATION
    assert len(signal.source_ids) == 1


def test_pedagogical_signal_does_not_confirm_with_no_observations() -> None:
    signal = evaluate_pedagogical_signal([])

    assert signal.confirmed is False
    assert signal.source_ids == ()


# --- decide_change_type -----------------------------------------------------------


@pytest.mark.parametrize(
    "confirmed_kinds,expected",
    [
        (frozenset({SignalKind.ATTENDANCE, SignalKind.PEDAGOGICAL_OBSERVATION}), TrajectoryChangeType.ATTENDANCE_DROP),
        (frozenset({SignalKind.GRADE, SignalKind.PEDAGOGICAL_OBSERVATION}), TrajectoryChangeType.GRADE_DROP),
        (
            frozenset({SignalKind.ASSIGNMENTS, SignalKind.PEDAGOGICAL_OBSERVATION}),
            TrajectoryChangeType.MISSING_ASSIGNMENTS_INCREASE,
        ),
        (frozenset({SignalKind.ATTENDANCE, SignalKind.GRADE}), TrajectoryChangeType.COMBINED_DETERIORATION),
        (
            frozenset({SignalKind.ATTENDANCE, SignalKind.GRADE, SignalKind.ASSIGNMENTS}),
            TrajectoryChangeType.COMBINED_DETERIORATION,
        ),
        (
            frozenset(
                {
                    SignalKind.ATTENDANCE,
                    SignalKind.GRADE,
                    SignalKind.ASSIGNMENTS,
                    SignalKind.PEDAGOGICAL_OBSERVATION,
                }
            ),
            TrajectoryChangeType.COMBINED_DETERIORATION,
        ),
    ],
)
def test_decide_change_type_mapping_table(confirmed_kinds, expected) -> None:
    assert decide_change_type(confirmed_kinds) == expected


def test_decide_change_type_raises_without_a_core_signal() -> None:
    with pytest.raises(ValueError):
        decide_change_type(frozenset({SignalKind.PEDAGOGICAL_OBSERVATION}))


# --- build_description -------------------------------------------------------------


def test_build_description_single_kind() -> None:
    text = build_description(frozenset({SignalKind.ATTENDANCE}), "3º Bimestre")

    assert text == "Mudança recente: queda de frequência — 3º Bimestre"


def test_build_description_two_kinds_uses_fixed_order_and_e() -> None:
    text = build_description(
        frozenset({SignalKind.PEDAGOGICAL_OBSERVATION, SignalKind.ATTENDANCE}), "3º Bimestre"
    )

    assert text == "Mudança recente: queda de frequência e registro pedagógico recente — 3º Bimestre"


def test_build_description_three_kinds() -> None:
    text = build_description(
        frozenset({SignalKind.ATTENDANCE, SignalKind.GRADE, SignalKind.ASSIGNMENTS}), "3º Bimestre"
    )

    assert text == (
        "Mudança recente: queda de frequência, queda de notas e aumento de "
        "atividades pendentes — 3º Bimestre"
    )


def test_build_description_never_uses_diagnostic_language() -> None:
    text = build_description(frozenset({SignalKind.ATTENDANCE}), "3º Bimestre")

    for forbidden in ("risco", "evasão", "chance", "predição", "score"):
        assert forbidden not in text.lower()


# --- evaluate_convergence -----------------------------------------------------------


def test_evaluate_convergence_with_two_confirmed_signals_returns_change() -> None:
    signals = [
        Signal(confirmed=True, kind=SignalKind.ATTENDANCE, source_ids=(uuid.uuid4(),)),
        Signal(confirmed=True, kind=SignalKind.PEDAGOGICAL_OBSERVATION, source_ids=(uuid.uuid4(),)),
        Signal(confirmed=False, kind=SignalKind.GRADE),
        Signal(confirmed=False, kind=SignalKind.ASSIGNMENTS),
    ]

    result = evaluate_convergence(signals)

    assert result.change_type == TrajectoryChangeType.ATTENDANCE_DROP
    assert len(result.confirmed_signals) == 2
    assert result.concerning_signal is None


def test_evaluate_convergence_with_exactly_one_confirmed_signal_returns_concerning_factor() -> None:
    signals = [
        Signal(confirmed=True, kind=SignalKind.GRADE, source_ids=(uuid.uuid4(),)),
        Signal(confirmed=False, kind=SignalKind.ATTENDANCE),
        Signal(confirmed=False, kind=SignalKind.ASSIGNMENTS),
        Signal(confirmed=False, kind=SignalKind.PEDAGOGICAL_OBSERVATION),
    ]

    result = evaluate_convergence(signals)

    assert result.change_type is None
    assert result.confirmed_signals == ()
    assert result.concerning_signal is not None
    assert result.concerning_signal.kind == SignalKind.GRADE


def test_evaluate_convergence_with_no_confirmed_signals_returns_nothing() -> None:
    signals = [
        Signal(confirmed=False, kind=SignalKind.ATTENDANCE),
        Signal(confirmed=False, kind=SignalKind.GRADE),
        Signal(confirmed=False, kind=SignalKind.ASSIGNMENTS),
        Signal(confirmed=False, kind=SignalKind.PEDAGOGICAL_OBSERVATION),
    ]

    result = evaluate_convergence(signals)

    assert result.change_type is None
    assert result.confirmed_signals == ()
    assert result.concerning_signal is None
