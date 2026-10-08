"""Covers every row of the spec's I/O & Edge-Case Matrix for `GET
/students/{id}/trajectory`."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.assignment_submission import AssignmentSubmissionStatus
from app.domain.attendance import AttendanceStatus
from app.domain.student import DatasetSplit
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    AssignmentModel,
    AssignmentSubmissionModel,
    AttendanceRecordModel,
    ClassroomModel,
    GradeModel,
    StudentModel,
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
    }
    assert "synthetic_profile" not in body
    assert Decimal(body["attendance_rate"]) == Decimal("0.5")
    assert Decimal(body["attendance_trend"]) == Decimal("-0.5")
    assert Decimal(body["grade_average"]) == Decimal("8.00")
    assert Decimal(body["grade_trend"]) == Decimal("2.00")
    assert body["missing_assignments_count"] == 1
    assert body["missing_assignment_delta"] == 1


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
