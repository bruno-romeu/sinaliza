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
    build_concerning_description,
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


def _observation(
    day: date = date(2026, 9, 1), registers_concern: bool = True
) -> PedagogicalObservation:
    from datetime import datetime, timezone

    return PedagogicalObservation(
        id=uuid.uuid4(),
        student_id=STUDENT_ID,
        author_user_id=AUTHOR_ID,
        text="Observação de teste.",
        created_at=datetime(day.year, day.month, day.day, 12, 0, tzinfo=timezone.utc),
        registers_concern=registers_concern,
    )


# --- evaluate_attendance_signal -------------------------------------------------


def test_attendance_signal_confirms_when_rate_below_threshold() -> None:
    current = [_attendance(date(2026, 9, 1), AttendanceStatus.ABSENT_UNJUSTIFIED)] * 3 + [
        _attendance(date(2026, 9, 2), AttendanceStatus.PRESENT)
    ]
    signal = evaluate_attendance_signal(current, [])

    assert signal.confirmed is True
    assert signal.kind == SignalKind.ATTENDANCE
    # spec-ui-3: only the absences are cited, never the days present.
    absences = [record for record in current if record.status != AttendanceStatus.PRESENT]
    assert signal.source_ids == tuple(record.id for record in absences)


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


def test_grade_signal_confirms_when_average_drops_below_own_habitual_low() -> None:
    # Earlier averages 7.0 and 6.5 -> habitual low 6.5; 5.5 is 1.0 below it.
    signal = evaluate_grade_signal([_grade("5.50")], [[_grade("7.00")], [_grade("6.50")]])

    assert signal.confirmed is True
    assert signal.kind == SignalKind.GRADE
    assert len(signal.source_ids) == 1


def test_grade_signal_ignores_a_low_but_stable_average() -> None:
    """spec-ui-3: a student who always had low grades is not a "queda"."""
    signal = evaluate_grade_signal([_grade("3.50")], [[_grade("3.00")], [_grade("3.10")]])

    assert signal.confirmed is False


def test_grade_signal_does_not_confirm_with_a_drop_smaller_than_one_point() -> None:
    signal = evaluate_grade_signal([_grade("6.60")], [[_grade("7.50")], [_grade("8.00")]])

    assert signal.confirmed is False


def test_grade_signal_needs_an_earlier_period_to_compare() -> None:
    assert evaluate_grade_signal([_grade("1.00")], []).confirmed is False
    assert evaluate_grade_signal([_grade("1.00")], [[]]).confirmed is False


def test_grade_signal_does_not_confirm_with_no_data() -> None:
    signal = evaluate_grade_signal([], [])

    assert signal.confirmed is False
    assert signal.source_ids == ()


# --- evaluate_assignments_signal --------------------------------------------------


def test_assignments_signal_confirms_two_above_the_highest_earlier_count() -> None:
    a1, a2 = _assignment(), _assignment()
    submissions_by_assignment = {
        a1.id: [_submission(a1.id, AssignmentSubmissionStatus.NOT_DELIVERED)],
        a2.id: [_submission(a2.id, AssignmentSubmissionStatus.PARTIAL)],
    }

    # Earlier períodos had 0 missing each; now 2 -> 2 above the habitual high.
    signal = evaluate_assignments_signal([a1, a2], [[], []], submissions_by_assignment)

    assert signal.confirmed is True
    assert signal.kind == SignalKind.ASSIGNMENTS
    assert len(signal.source_ids) == 2


def test_assignments_signal_ignores_a_count_the_student_always_had() -> None:
    """spec-ui-3: 2 missing every período is the student's own pattern."""
    current = [_assignment(), _assignment()]
    earlier = [_assignment(date(2026, 6, 1)), _assignment(date(2026, 6, 2))]
    submissions_by_assignment = {
        a.id: [_submission(a.id, AssignmentSubmissionStatus.NOT_DELIVERED)] for a in current + earlier
    }

    signal = evaluate_assignments_signal(current, [earlier], submissions_by_assignment)

    assert signal.confirmed is False


def test_assignments_signal_needs_an_earlier_period_to_compare() -> None:
    a1, a2, a3 = _assignment(), _assignment(), _assignment()
    submissions_by_assignment = {
        a.id: [_submission(a.id, AssignmentSubmissionStatus.NOT_DELIVERED)] for a in (a1, a2, a3)
    }

    signal = evaluate_assignments_signal([a1, a2, a3], [], submissions_by_assignment)

    assert signal.confirmed is False


def test_assignments_signal_ignores_assignments_with_zero_submissions() -> None:
    """Design Notes: never counts an assignment with zero submissions
    registered — only ones with a real citable NOT_DELIVERED/PARTIAL row."""
    a1, a2 = _assignment(), _assignment()
    # a1 has no submission at all; a2 has a DELIVERED one (not missing).
    submissions_by_assignment = {a2.id: [_submission(a2.id, AssignmentSubmissionStatus.DELIVERED)]}

    signal = evaluate_assignments_signal([a1, a2], [[]], submissions_by_assignment)

    assert signal.confirmed is False
    assert signal.source_ids == ()


# --- evaluate_pedagogical_signal --------------------------------------------------


def test_pedagogical_signal_confirms_with_a_concern_marked_observation() -> None:
    concern = _observation()
    signal = evaluate_pedagogical_signal([_observation(registers_concern=False), concern])

    assert signal.confirmed is True
    assert signal.kind == SignalKind.PEDAGOGICAL_OBSERVATION
    assert signal.source_ids == (concern.id,)


def test_pedagogical_signal_ignores_neutral_observations() -> None:
    """spec-ui-3: "Frequência dentro da faixa habitual" is not a signal."""
    signal = evaluate_pedagogical_signal([_observation(registers_concern=False)])

    assert signal.confirmed is False
    assert signal.source_ids == ()


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

    assert text == "Queda de frequência no 3º Bimestre"


def test_build_description_two_kinds_uses_fixed_order_and_e() -> None:
    text = build_description(
        frozenset({SignalKind.PEDAGOGICAL_OBSERVATION, SignalKind.ATTENDANCE}), "3º Bimestre"
    )

    assert text == "Queda de frequência e preocupação registrada pela equipe no 3º Bimestre"


def test_build_description_three_kinds() -> None:
    text = build_description(
        frozenset({SignalKind.ATTENDANCE, SignalKind.GRADE, SignalKind.ASSIGNMENTS}), "3º Bimestre"
    )

    assert text == (
        "Queda de frequência, queda de notas e aumento de "
        "atividades pendentes no 3º Bimestre"
    )


def test_build_description_has_no_dash_and_no_prefix() -> None:
    """spec-ui-1: on-screen text never uses dashes, and the change label is
    the surface's job, not part of the description."""
    text = build_description(
        frozenset({SignalKind.ATTENDANCE, SignalKind.GRADE}), "3º Bimestre"
    )

    assert "—" not in text
    assert "–" not in text
    assert not text.startswith("Mudança recente")


def test_build_concerning_description_reads_as_isolated_signal() -> None:
    text = build_concerning_description(SignalKind.GRADE, "3º Bimestre")

    assert text == "Sinal isolado: queda de notas no 3º Bimestre"
    assert "Mudança" not in text


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
