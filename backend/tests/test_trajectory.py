"""Covers every row of the spec's I/O & Edge-Case Matrix for `GET
/students/{id}/trajectory`."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.assignment_submission import AssignmentSubmissionStatus
from app.domain.attendance import AttendanceStatus
from app.domain.student import DatasetSplit
from app.domain.trajectory_change import TrajectoryChangeType
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    AssignmentModel,
    AssignmentSubmissionModel,
    AttendanceRecordModel,
    ClassroomModel,
    GradeModel,
    PedagogicalObservationModel,
    StudentModel,
    TrajectoryChangeModel,
    TrajectoryChangeSourceModel,
)

STUDENT_NOT_FOUND_BODY = {
    "error": {"code": "student_not_found", "message": "Estudante não encontrado."}
}

# Falls inside `seeded_academic_period`'s window (2026-07-27 .. 2026-09-25).
AS_OF = "2026-09-24"


@pytest.fixture(autouse=True)
def _frozen_as_of(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pins `as_of()` to a fixed date for every test in this file so window
    math is deterministic — tests that need a different "today" override it
    again locally (`monkeypatch` stacks and unwinds safely)."""
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", AS_OF)


def _auth_headers(client: TestClient, seeded_user) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": seeded_user.email, "password": "Senha-Correta-123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- Happy path -----------------------------------------------------------------


def test_trajectory_happy_path_returns_200_with_six_indicators(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    previous_period = AcademicPeriodModel(
        label="2º Bimestre Teste",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 7, 26),
        order_index=2,
    )
    db_session.add(previous_period)
    db_session.flush()

    db_session.add_all(
        [
            # current window [2026-08-25, 2026-09-24]
            AttendanceRecordModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 9, 20),
                status=AttendanceStatus.PRESENT,
            ),
            AttendanceRecordModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 9, 21),
                status=AttendanceStatus.ABSENT_UNJUSTIFIED,
            ),
            # previous window [2026-07-26, 2026-08-25)
            AttendanceRecordModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 8, 10),
                status=AttendanceStatus.PRESENT,
            ),
            GradeModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                subject="Matemática",
                period_id=seeded_academic_period.id,
                date=date(2026, 9, 20),
                value=Decimal("8.00"),
            ),
            GradeModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                subject="Matemática",
                period_id=previous_period.id,
                date=date(2026, 6, 15),
                value=Decimal("6.00"),
            ),
        ]
    )
    assignment = AssignmentModel(
        classroom_id=seeded_classroom.id,
        subject="Matemática",
        period_id=seeded_academic_period.id,
        due_date=date(2026, 9, 22),
    )
    db_session.add(assignment)
    db_session.flush()
    db_session.add(
        AssignmentSubmissionModel(
            assignment_id=assignment.id,
            student_id=seeded_enrolled_student.id,
            status=AssignmentSubmissionStatus.NOT_DELIVERED,
            date=date(2026, 9, 22),
        )
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "attendance_rate",
        "attendance_trend",
        "grade_average",
        "grade_trend",
        "missing_assignments_count",
        "missing_assignment_delta",
        "trajectory_change",
        "concerning_factor",
    }
    assert "synthetic_profile" not in body
    assert Decimal(body["attendance_rate"]) == Decimal("0.5")
    assert Decimal(body["attendance_trend"]) == Decimal("-0.5")
    assert Decimal(body["grade_average"]) == Decimal("8.00")
    assert Decimal(body["grade_trend"]) == Decimal("2.00")
    assert body["missing_assignments_count"] == 1
    assert body["missing_assignment_delta"] == 1

    # Story 3.2: within the período vigente, only the ATTENDANCE signal
    # confirms here (rate 2/3 < 0.75) — grade/assignments/pedagogical don't —
    # so this is a single isolated signal, surfaced as an ephemeral
    # `concerning_factor`, never persisted.
    assert body["trajectory_change"] is None
    assert body["concerning_factor"] == {
        "kind": "ATTENDANCE",
        "description": "Mudança recente: queda de frequência — 3º Bimestre Teste",
    }


# --- No data in window ------------------------------------------------------------


def test_trajectory_with_no_data_returns_200_with_none_and_zero(
    client: TestClient,
    seeded_user,
    db_session: Session,
) -> None:
    bare_student = StudentModel(name="Estudante Sem Dados", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add(bare_student)
    db_session.commit()

    response = client.get(
        f"/students/{bare_student.id}/trajectory",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["attendance_rate"] is None
    assert body["attendance_trend"] is None
    assert body["grade_average"] is None
    assert body["grade_trend"] is None
    assert body["missing_assignments_count"] == 0
    assert body["trajectory_change"] is None
    assert body["concerning_factor"] is None
    assert body["missing_assignment_delta"] == 0


# --- Estudante inexistente / TRAIN ------------------------------------------------


def test_trajectory_for_unknown_student_returns_404(client: TestClient, seeded_user) -> None:
    response = client.get(
        f"/students/{uuid.uuid4()}/trajectory",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 404
    assert response.json() == STUDENT_NOT_FOUND_BODY


def test_trajectory_for_train_split_student_returns_identical_404(
    client: TestClient, seeded_user, db_session: Session
) -> None:
    """Spec I/O Matrix: a `TRAIN`-split student must 404 with the exact same
    body as a nonexistent one — never distinguishable, never leaking the
    split."""
    train_student = StudentModel(name="Aluno de Treino", dataset_split=DatasetSplit.TRAIN)
    db_session.add(train_student)
    db_session.commit()

    response = client.get(
        f"/students/{train_student.id}/trajectory",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 404
    assert response.json() == STUDENT_NOT_FOUND_BODY


# --- as_of() override --------------------------------------------------------------


def test_trajectory_as_of_override_changes_the_window(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given `SINALIZA_DEMO_AS_OF` set, the window is computed from that
    date, never the real one — proven here by moving "today" earlier until
    a previously-in-window record falls out of it."""
    db_session.add(
        AttendanceRecordModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            date=date(2026, 9, 20),
            status=AttendanceStatus.PRESENT,
        )
    )
    db_session.commit()

    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", "2026-08-01")
    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    assert response.json()["attendance_rate"] is None


# --- Concorrência -------------------------------------------------------------------


def test_trajectory_two_requests_for_same_student_produce_identical_results(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
) -> None:
    db_session.add(
        AttendanceRecordModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            date=date(2026, 9, 20),
            status=AttendanceStatus.PRESENT,
        )
    )
    db_session.commit()
    headers = _auth_headers(client, seeded_user)

    first = client.get(f"/students/{seeded_enrolled_student.id}/trajectory", headers=headers)
    second = client.get(f"/students/{seeded_enrolled_student.id}/trajectory", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


# --- window_days override ------------------------------------------------------------


def test_trajectory_window_days_query_param_overrides_default(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
) -> None:
    """A record just outside the default 30-day window (2026-08-20, 35 days
    before `AS_OF`) is picked up once `?window_days=40` widens the window."""
    db_session.add(
        AttendanceRecordModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            date=date(2026, 8, 20),
            status=AttendanceStatus.PRESENT,
        )
    )
    db_session.commit()
    headers = _auth_headers(client, seeded_user)

    default_window = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory", headers=headers
    )
    widened_window = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory?window_days=40", headers=headers
    )

    assert default_window.json()["attendance_rate"] is None
    assert widened_window.json()["attendance_rate"] == "1.0000"


# --- Unauthenticated ------------------------------------------------------------------


def test_trajectory_without_bearer_token_returns_401(
    client: TestClient, seeded_enrolled_student: StudentModel
) -> None:
    response = client.get(f"/students/{seeded_enrolled_student.id}/trajectory")

    assert response.status_code == 401
    assert "error" in response.json()


# --- window_days validation ---------------------------------------------------------


@pytest.mark.parametrize("window_days", [0, -1])
def test_trajectory_window_days_non_positive_returns_422(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    window_days: int,
) -> None:
    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory?window_days={window_days}",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422


def test_trajectory_window_days_above_upper_bound_returns_422(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
) -> None:
    """`window_days` is capped (`le=3650`) so a huge value can never overflow
    `date - timedelta(days=2*window_days)` into a raw 500."""
    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory?window_days=4000",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422


# --- AcademicPeriod resolution boundaries -------------------------------------------


def test_trajectory_as_of_on_period_start_date_boundary_is_current_period(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`as_of_date == period.start_date` must still resolve that period as
    current (inclusive boundary: `start_date <= as_of_date <= end_date`)."""
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", seeded_academic_period.start_date.isoformat())
    db_session.add(
        GradeModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            subject="Matemática",
            period_id=seeded_academic_period.id,
            date=seeded_academic_period.start_date,
            value=Decimal("7.00"),
        )
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    assert Decimal(response.json()["grade_average"]) == Decimal("7.00")


def test_trajectory_as_of_on_period_end_date_boundary_is_current_period(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`as_of_date == period.end_date` must still resolve that period as
    current (inclusive boundary: `start_date <= as_of_date <= end_date`)."""
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", seeded_academic_period.end_date.isoformat())
    db_session.add(
        GradeModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            subject="Matemática",
            period_id=seeded_academic_period.id,
            date=seeded_academic_period.end_date,
            value=Decimal("9.00"),
        )
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    assert Decimal(response.json()["grade_average"]) == Decimal("9.00")


def test_trajectory_as_of_not_covered_by_any_existing_period_has_no_current_period(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Distinct from the "zero periods exist" case: here a period row exists
    in the DB, but `as_of_date` falls outside every period's window, so no
    current/previous period is resolved and grade indicators stay `None`
    even though a grade row exists (it belongs to a period that isn't
    "vigente" for this `as_of_date`)."""
    day_after_period_ends = seeded_academic_period.end_date + timedelta(days=1)
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", day_after_period_ends.isoformat())
    db_session.add(
        GradeModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            subject="Matemática",
            period_id=seeded_academic_period.id,
            date=seeded_academic_period.end_date,
            value=Decimal("5.00"),
        )
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grade_average"] is None
    assert body["grade_trend"] is None
    assert body["trajectory_change"] is None
    assert body["concerning_factor"] is None


# --- Story 3.2: convergência de sinais -----------------------------------------------


def _add_low_attendance(
    db_session: Session, student_id, classroom_id, present_count: int, absent_count: int
) -> None:
    """Writes `present_count` PRESENT + `absent_count` ABSENT_UNJUSTIFIED
    records, all dated inside `seeded_academic_period`'s window, so the
    período-scoped ATTENDANCE signal reads a low rate."""
    day = date(2026, 8, 1)
    for _ in range(present_count):
        db_session.add(
            AttendanceRecordModel(
                student_id=student_id, classroom_id=classroom_id, date=day, status=AttendanceStatus.PRESENT
            )
        )
        day += timedelta(days=1)
    for _ in range(absent_count):
        db_session.add(
            AttendanceRecordModel(
                student_id=student_id,
                classroom_id=classroom_id,
                date=day,
                status=AttendanceStatus.ABSENT_UNJUSTIFIED,
            )
        )
        day += timedelta(days=1)


def test_trajectory_two_confirmed_signals_creates_trajectory_change_with_sources(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    """Spec I/O Matrix: "Convergência (2+ sinais)" — ATTENDANCE (rate 1/3 <
    0.75) + PEDAGOGICAL_OBSERVATION both confirm inside the período vigente,
    so a `TrajectoryChange` is upserted with its `TrajectoryChangeSource`s in
    the same transaction, and the response includes it."""
    _add_low_attendance(db_session, seeded_enrolled_student.id, seeded_classroom.id, 1, 2)
    db_session.add(
        PedagogicalObservationModel(
            student_id=seeded_enrolled_student.id,
            author_user_id=seeded_user.id,
            text="Observação de teste.",
            created_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["concerning_factor"] is None
    change = body["trajectory_change"]
    assert change is not None
    assert change["type"] == "ATTENDANCE_DROP"
    assert change["period_id"] == str(seeded_academic_period.id)
    assert change["description"] == (
        "Mudança recente: queda de frequência e registro pedagógico recente "
        "— 3º Bimestre Teste"
    )
    detected_at = datetime.fromisoformat(change["detected_at"].replace("Z", "+00:00"))
    assert detected_at == datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc)

    db_rows = db_session.execute(select(TrajectoryChangeModel)).scalars().all()
    assert len(db_rows) == 1
    assert db_rows[0].student_id == seeded_enrolled_student.id
    assert db_rows[0].period_id == seeded_academic_period.id

    source_rows = db_session.execute(select(TrajectoryChangeSourceModel)).scalars().all()
    # 3 attendance records + 1 pedagogical observation cited.
    assert len(source_rows) == 4
    assert all(row.trajectory_change_id == db_rows[0].id for row in source_rows)


def test_trajectory_pedagogical_observation_after_as_of_is_excluded_from_signal(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    """AD-11 leak-prevention invariant (`filter_as_of`, mirrored from the
    attendance/assignment repositories' own precedent): a
    `PedagogicalObservation` dated after `as_of()` — even if still inside
    `seeded_academic_period`'s date range — must never confirm the
    PEDAGOGICAL_OBSERVATION signal. Without this test, removing
    `list_by_student_in_range`'s `filter_as_of` call would pass every other
    test in this file undetected, since they only ever seed observations
    dated before `as_of()` (Review Findings #23)."""
    _add_low_attendance(db_session, seeded_enrolled_student.id, seeded_classroom.id, 1, 2)
    db_session.add(
        PedagogicalObservationModel(
            student_id=seeded_enrolled_student.id,
            author_user_id=seeded_user.id,
            text="Observação futura, não deve contar ainda.",
            # After AS_OF ("2026-09-24") but still inside the período
            # vigente (ends 2026-09-25).
            created_at=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    # Only ATTENDANCE confirms (the future-dated observation must not count
    # as a second signal) — exactly one confirmed signal yields a
    # `concerning_factor`, never a persisted `trajectory_change`.
    assert body["trajectory_change"] is None
    assert body["concerning_factor"] == {
        "kind": "ATTENDANCE",
        "description": "Mudança recente: queda de frequência — 3º Bimestre Teste",
    }
    assert db_session.execute(select(TrajectoryChangeModel)).scalars().all() == []


def test_trajectory_recompute_same_period_replaces_description_and_sources(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec I/O Matrix: "Recálculo do mesmo período" — same `(student_id,
    type, period_id)` upsert key both times (`COMBINED_DETERIORATION`, since
    ATTENDANCE stays confirmed throughout and a second core signal is
    confirmed both times), but `description`/`TrajectoryChangeSource` rows
    are fully substituted (delete+reinsert) once the confirming combination
    changes. `detected_at` is reader-derived from `as_of()` on every call
    (Implementation Notes), so it must also advance on recompute — this test
    runs the second `GET` under a later `SINALIZA_DEMO_AS_OF` (still inside
    `seeded_academic_period`) to prove `ON CONFLICT ... DO UPDATE` actually
    refreshes it, not just `description`/sources (Review Findings #22)."""
    _add_low_attendance(db_session, seeded_enrolled_student.id, seeded_classroom.id, 1, 2)
    db_session.add(
        GradeModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            subject="Matemática",
            period_id=seeded_academic_period.id,
            date=date(2026, 9, 1),
            value=Decimal("3.00"),
        )
    )
    db_session.commit()
    headers = _auth_headers(client, seeded_user)

    first = client.get(f"/students/{seeded_enrolled_student.id}/trajectory", headers=headers)
    assert first.status_code == 200
    first_change = first.json()["trajectory_change"]
    assert first_change["type"] == "COMBINED_DETERIORATION"
    assert first_change["description"] == (
        "Mudança recente: queda de frequência e queda de notas — 3º Bimestre Teste"
    )

    first_row = db_session.execute(select(TrajectoryChangeModel)).scalars().one()
    first_id = first_row.id

    # Grade recovers above the threshold (no longer confirms); two
    # assignments with citable missing submissions make ASSIGNMENTS confirm
    # instead — ATTENDANCE stays confirmed, so the type is still
    # COMBINED_DETERIORATION (same upsert key), but the confirming pair (and
    # therefore the description/sources) changed.
    db_session.add(
        GradeModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            subject="Matemática",
            period_id=seeded_academic_period.id,
            date=date(2026, 9, 2),
            value=Decimal("9.00"),
        )
    )
    for i in range(2):
        assignment = AssignmentModel(
            classroom_id=seeded_classroom.id,
            subject="Matemática",
            period_id=seeded_academic_period.id,
            due_date=date(2026, 9, 10 + i),
        )
        db_session.add(assignment)
        db_session.flush()
        db_session.add(
            AssignmentSubmissionModel(
                assignment_id=assignment.id,
                student_id=seeded_enrolled_student.id,
                status=AssignmentSubmissionStatus.NOT_DELIVERED,
                date=date(2026, 9, 10 + i),
            )
        )
    db_session.commit()

    # Still inside `seeded_academic_period` (2026-07-27..2026-09-25) — same
    # period, later "today", so `detected_at` must move forward on recompute.
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", "2026-09-25")

    second = client.get(f"/students/{seeded_enrolled_student.id}/trajectory", headers=headers)
    assert second.status_code == 200
    second_change = second.json()["trajectory_change"]
    assert second_change["type"] == "COMBINED_DETERIORATION"
    assert second_change["description"] == (
        "Mudança recente: queda de frequência e aumento de atividades "
        "pendentes — 3º Bimestre Teste"
    )
    assert second_change["detected_at"] != first_change["detected_at"]
    assert second_change["detected_at"].startswith("2026-09-25")

    rows = db_session.execute(select(TrajectoryChangeModel)).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == first_id
    assert rows[0].description == second_change["description"]
    assert rows[0].detected_at == datetime(2026, 9, 25, 0, 0, tzinfo=timezone.utc)

    source_types = {
        row.source_type
        for row in db_session.execute(select(TrajectoryChangeSourceModel)).scalars().all()
    }
    assert "GRADE" not in source_types
    assert "ASSIGNMENT_SUBMISSION" in source_types
    assert "ATTENDANCE_RECORD" in source_types


def test_trajectory_recompute_leaves_prior_period_change_untouched(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    """Spec I/O Matrix: "Recálculo, sinais pararam de confirmar" — a
    `TrajectoryChange` already recorded for a previous período is never
    deleted/reverted by a recomputation of the (non-converging) período
    vigente; `TrajectoryChange` is an immutable event (spec Boundaries &
    Constraints)."""
    previous_period = AcademicPeriodModel(
        label="2º Bimestre Teste",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 7, 26),
        order_index=2,
    )
    db_session.add(previous_period)
    db_session.flush()

    prior_change = TrajectoryChangeModel(
        student_id=seeded_enrolled_student.id,
        type=TrajectoryChangeType.GRADE_DROP,
        period_id=previous_period.id,
        detected_at=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
        description="Mudança recente: queda de notas — 2º Bimestre Teste",
    )
    db_session.add(prior_change)
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trajectory_change"] is None
    assert body["concerning_factor"] is None

    rows = db_session.execute(select(TrajectoryChangeModel)).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == prior_change.id
    assert rows[0].period_id == previous_period.id
    assert rows[0].description == "Mudança recente: queda de notas — 2º Bimestre Teste"


def test_trajectory_two_requests_with_convergence_produce_identical_change_no_duplicate_row(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    """Spec I/O Matrix: "Concorrência" — the `ON CONFLICT` upsert resolves
    both requests to the exact same row, never a duplicate."""
    _add_low_attendance(db_session, seeded_enrolled_student.id, seeded_classroom.id, 1, 2)
    db_session.add(
        PedagogicalObservationModel(
            student_id=seeded_enrolled_student.id,
            author_user_id=seeded_user.id,
            text="Observação de teste.",
            created_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        )
    )
    db_session.commit()
    headers = _auth_headers(client, seeded_user)

    first = client.get(f"/students/{seeded_enrolled_student.id}/trajectory", headers=headers)
    second = client.get(f"/students/{seeded_enrolled_student.id}/trajectory", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["trajectory_change"] == second.json()["trajectory_change"]

    rows = db_session.execute(select(TrajectoryChangeModel)).scalars().all()
    assert len(rows) == 1
    source_rows = db_session.execute(select(TrajectoryChangeSourceModel)).scalars().all()
    assert len(source_rows) == 4
