"""Covers every row of the spec's I/O & Edge-Case Matrix for `GET
/academic-periods` and `POST /grades`."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.student import DatasetSplit
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    ClassroomModel,
    EnrollmentModel,
    GradeModel,
    StudentModel,
)

CLASSROOM_NOT_FOUND_BODY = {
    "error": {"code": "classroom_not_found", "message": "Turma não encontrada."}
}
ACADEMIC_PERIOD_NOT_FOUND_BODY = {
    "error": {"code": "academic_period_not_found", "message": "Período letivo não encontrado."}
}
STUDENT_NOT_ENROLLED_BODY = {
    "error": {
        "code": "student_not_enrolled",
        "message": "Estudante não está matriculado nesta turma.",
    }
}


def _auth_headers(client: TestClient, seeded_user) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": seeded_user.email, "password": "Senha-Correta-123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _grade_payload(
    student_id: uuid.UUID,
    classroom_id: uuid.UUID,
    period_id: uuid.UUID,
    value: str = "8.50",
) -> dict:
    return {
        "student_id": str(student_id),
        "classroom_id": str(classroom_id),
        "subject": "Matemática",
        "period_id": str(period_id),
        "date": "2026-09-24",
        "value": value,
    }


# --- GET /academic-periods -----------------------------------------------------


def test_list_academic_periods_returns_seeded_period(
    client: TestClient, seeded_user, seeded_academic_period: AcademicPeriodModel
) -> None:
    response = client.get("/academic-periods", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    body = response.json()
    assert {
        "id": str(seeded_academic_period.id),
        "label": "3º Bimestre Teste",
        "start_date": "2026-07-27",
        "end_date": "2026-09-25",
        "order_index": 3,
    } in body


def test_list_academic_periods_without_bearer_token_returns_401(client: TestClient) -> None:
    response = client.get("/academic-periods")

    assert response.status_code == 401
    assert "error" in response.json()
    assert "detail" not in response.json()


# --- Happy path -------------------------------------------------------------


def test_register_grade_happy_path_returns_201_and_persists(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    response = client.post(
        "/grades",
        json=_grade_payload(
            seeded_enrolled_student.id, seeded_classroom.id, seeded_academic_period.id
        ),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["student_id"] == str(seeded_enrolled_student.id)
    assert body["classroom_id"] == str(seeded_classroom.id)
    assert body["period_id"] == str(seeded_academic_period.id)
    assert body["subject"] == "Matemática"
    assert body["date"] == "2026-09-24"
    assert Decimal(body["value"]) == Decimal("8.50")

    persisted = (
        db_session.query(GradeModel)
        .filter(GradeModel.student_id == seeded_enrolled_student.id)
        .one()
    )
    assert persisted.value == Decimal("8.50")


def test_register_grade_allows_second_grade_same_student_subject_period_date(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    """Spec Boundaries & Constraints: `Grade` carries no UNIQUE constraint —
    a student may legitimately receive multiple assessments in the same
    período, unlike `AttendanceRecord`."""
    headers = _auth_headers(client, seeded_user)
    payload = _grade_payload(
        seeded_enrolled_student.id, seeded_classroom.id, seeded_academic_period.id
    )

    first = client.post("/grades", json=payload, headers=headers)
    second = client.post("/grades", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    count = (
        db_session.query(GradeModel)
        .filter(GradeModel.student_id == seeded_enrolled_student.id)
        .count()
    )
    assert count == 2


# --- Out-of-range value (API bypass) -------------------------------------------


def test_register_grade_out_of_range_value_returns_standard_422(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
) -> None:
    response = client.post(
        "/grades",
        json=_grade_payload(
            seeded_enrolled_student.id,
            seeded_classroom.id,
            seeded_academic_period.id,
            value="15.00",
        ),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422
    body = response.json()
    # Standard FastAPI/Pydantic validation body, not the `AppError` envelope.
    assert "detail" in body
    assert "error" not in body


# --- DB-level bypass ----------------------------------------------------------


def test_grade_value_check_constraint_is_enforced_at_the_database_level(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
) -> None:
    """Proves the constraint is real at the DB level — inserts a
    `GradeModel` with `value=15` directly against the table, bypassing
    `RegisterGradeService`/schema validation entirely."""
    invalid = GradeModel(
        student_id=seeded_enrolled_student.id,
        classroom_id=seeded_classroom.id,
        subject="Matemática",
        period_id=seeded_academic_period.id,
        date=date(2026, 9, 24),
        value=Decimal("15.00"),
    )
    db_session.add(invalid)
    with pytest.raises(IntegrityError):
        db_session.commit()
    # The SAVEPOINT-joined session (see conftest.db_session) auto-restarts a
    # fresh savepoint once the failed one ends — no manual rollback needed.


# --- Unauthenticated -----------------------------------------------------------


def test_register_grade_without_bearer_token_returns_401(
    client: TestClient,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
) -> None:
    response = client.post(
        "/grades",
        json=_grade_payload(
            seeded_enrolled_student.id, seeded_classroom.id, seeded_academic_period.id
        ),
    )

    assert response.status_code == 401
    assert "error" in response.json()


# --- Unknown classroom ---------------------------------------------------------


def test_register_grade_for_unknown_classroom_returns_404(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
) -> None:
    response = client.post(
        "/grades",
        json=_grade_payload(seeded_enrolled_student.id, uuid.uuid4(), seeded_academic_period.id),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 404
    assert response.json() == CLASSROOM_NOT_FOUND_BODY


# --- Unknown period -------------------------------------------------------------


def test_register_grade_for_unknown_period_returns_404(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    response = client.post(
        "/grades",
        json=_grade_payload(seeded_enrolled_student.id, seeded_classroom.id, uuid.uuid4()),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 404
    assert response.json() == ACADEMIC_PERIOD_NOT_FOUND_BODY


# --- Student not enrolled -------------------------------------------------------


def test_register_grade_for_student_not_enrolled_returns_422(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    other_classroom = ClassroomModel(name="Outra Turma", academic_year=2026)
    db_session.add(other_classroom)
    db_session.flush()
    unenrolled_student = StudentModel(name="Aluno Sem Matrícula", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add(unenrolled_student)
    db_session.commit()

    response = client.post(
        "/grades",
        json=_grade_payload(unenrolled_student.id, seeded_classroom.id, seeded_academic_period.id),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422
    assert response.json() == STUDENT_NOT_ENROLLED_BODY


def test_register_grade_for_train_split_student_returns_422(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    """AD-4/AD-11: `exists_enrollment` must apply the same `dataset_split =
    EVAL_DEMO` filter used by attendance — a `TRAIN`-split student who has a
    row in `enrollments` is never treated as validly enrolled for a grade
    write either."""
    train_student = StudentModel(name="Aluno de Treino", dataset_split=DatasetSplit.TRAIN)
    db_session.add(train_student)
    db_session.flush()
    db_session.add(EnrollmentModel(student_id=train_student.id, classroom_id=seeded_classroom.id))
    db_session.commit()

    response = client.post(
        "/grades",
        json=_grade_payload(train_student.id, seeded_classroom.id, seeded_academic_period.id),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422
    assert response.json() == STUDENT_NOT_ENROLLED_BODY
