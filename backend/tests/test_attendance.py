"""Covers every row of the spec's I/O & Edge-Case Matrix for `GET
/classrooms`, `GET /classrooms/{classroom_id}/students`, and `POST
/attendance`."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.attendance import AttendanceStatus
from app.domain.student import DatasetSplit
from app.infrastructure.db.models import (
    AttendanceRecordModel,
    ClassroomModel,
    EnrollmentModel,
    StudentModel,
)

DUPLICATE_ATTENDANCE_BODY = {
    "error": {
        "code": "duplicate_attendance",
        "message": "Já existe registro de presença para este aluno, turma e data.",
    }
}
CLASSROOM_NOT_FOUND_BODY = {
    "error": {"code": "classroom_not_found", "message": "Turma não encontrada."}
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


# --- Happy path -------------------------------------------------------------


def test_list_classrooms_returns_seeded_classroom(
    client: TestClient, seeded_user, seeded_classroom: ClassroomModel
) -> None:
    response = client.get("/classrooms", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    body = response.json()
    assert {"id": str(seeded_classroom.id), "name": "Turma Teste", "academic_year": 2026} in body


def test_list_enrolled_students_returns_matriculated_students(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    response = client.get(
        f"/classrooms/{seeded_classroom.id}/students", headers=_auth_headers(client, seeded_user)
    )

    assert response.status_code == 200
    assert response.json() == [
        {"id": str(seeded_enrolled_student.id), "name": seeded_enrolled_student.name}
    ]


def test_list_enrolled_students_excludes_train_split_students(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
) -> None:
    """AD-4/AD-11: the web application's reads always filter
    `dataset_split = EVAL_DEMO` via the shared repository-base filter — a
    `TRAIN`-split student enrolled in the same classroom must never leak
    into this list."""
    train_student = StudentModel(name="Aluno de Treino", dataset_split=DatasetSplit.TRAIN)
    db_session.add(train_student)
    db_session.flush()
    db_session.add(EnrollmentModel(student_id=train_student.id, classroom_id=seeded_classroom.id))
    db_session.commit()

    response = client.get(
        f"/classrooms/{seeded_classroom.id}/students", headers=_auth_headers(client, seeded_user)
    )

    assert response.status_code == 200
    returned_ids = {student["id"] for student in response.json()}
    assert str(seeded_enrolled_student.id) in returned_ids
    assert str(train_student.id) not in returned_ids


def test_register_attendance_happy_path_returns_201_and_persists(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
) -> None:
    response = client.post(
        "/attendance",
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(seeded_classroom.id),
            "date": "2026-09-23",
            "status": "PRESENT",
        },
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["student_id"] == str(seeded_enrolled_student.id)
    assert body["classroom_id"] == str(seeded_classroom.id)
    assert body["date"] == "2026-09-23"
    assert body["status"] == "PRESENT"

    persisted = (
        db_session.query(AttendanceRecordModel)
        .filter(AttendanceRecordModel.student_id == seeded_enrolled_student.id)
        .one()
    )
    assert persisted.status.value == "PRESENT"


# --- Duplicate ---------------------------------------------------------------


def test_register_attendance_duplicate_returns_409_with_no_second_row(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
) -> None:
    headers = _auth_headers(client, seeded_user)
    payload = {
        "student_id": str(seeded_enrolled_student.id),
        "classroom_id": str(seeded_classroom.id),
        "date": "2026-09-23",
        "status": "PRESENT",
    }

    first = client.post("/attendance", json=payload, headers=headers)
    assert first.status_code == 201

    second = client.post(
        "/attendance", json={**payload, "status": "ABSENT_JUSTIFIED"}, headers=headers
    )

    assert second.status_code == 409
    assert second.json() == DUPLICATE_ATTENDANCE_BODY

    count = (
        db_session.query(AttendanceRecordModel)
        .filter(AttendanceRecordModel.student_id == seeded_enrolled_student.id)
        .count()
    )
    assert count == 1


# --- DB-level bypass ----------------------------------------------------------


def test_attendance_unique_constraint_is_enforced_at_the_database_level(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    """Proves the constraint is real at the DB level — inserts a duplicate
    row directly against the table, bypassing `RegisterAttendanceService`
    entirely."""
    first = AttendanceRecordModel(
        student_id=seeded_enrolled_student.id,
        classroom_id=seeded_classroom.id,
        date=date(2026, 9, 23),
        status=AttendanceStatus.PRESENT,
    )
    db_session.add(first)
    db_session.commit()

    duplicate = AttendanceRecordModel(
        student_id=seeded_enrolled_student.id,
        classroom_id=seeded_classroom.id,
        date=date(2026, 9, 23),
        status=AttendanceStatus.ABSENT_UNJUSTIFIED,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    # The SAVEPOINT-joined session (see conftest.db_session) auto-restarts a
    # fresh savepoint once the failed one ends — no manual rollback needed.


# --- Unauthenticated -----------------------------------------------------------


def test_list_classrooms_without_bearer_token_returns_401(client: TestClient) -> None:
    response = client.get("/classrooms")

    assert response.status_code == 401
    assert "error" in response.json()
    assert "detail" not in response.json()


def test_list_enrolled_students_without_bearer_token_returns_401(
    client: TestClient, seeded_classroom: ClassroomModel
) -> None:
    response = client.get(f"/classrooms/{seeded_classroom.id}/students")

    assert response.status_code == 401
    assert "error" in response.json()


def test_register_attendance_without_bearer_token_returns_401(
    client: TestClient, seeded_classroom: ClassroomModel, seeded_enrolled_student: StudentModel
) -> None:
    response = client.post(
        "/attendance",
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(seeded_classroom.id),
            "date": "2026-09-23",
            "status": "PRESENT",
        },
    )

    assert response.status_code == 401
    assert "error" in response.json()


# --- Unknown classroom ---------------------------------------------------------


def test_list_enrolled_students_for_unknown_classroom_returns_404(
    client: TestClient, seeded_user
) -> None:
    response = client.get(
        f"/classrooms/{uuid.uuid4()}/students", headers=_auth_headers(client, seeded_user)
    )

    assert response.status_code == 404
    assert response.json() == CLASSROOM_NOT_FOUND_BODY


# --- Student not enrolled -------------------------------------------------------


def test_register_attendance_for_student_not_enrolled_returns_422(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    db_session: Session,
) -> None:
    other_classroom = ClassroomModel(name="Outra Turma", academic_year=2026)
    db_session.add(other_classroom)
    db_session.flush()
    unenrolled_student = StudentModel(name="Aluno Sem Matrícula", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add(unenrolled_student)
    db_session.commit()

    response = client.post(
        "/attendance",
        json={
            "student_id": str(unenrolled_student.id),
            "classroom_id": str(seeded_classroom.id),
            "date": "2026-09-23",
            "status": "PRESENT",
        },
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422
    assert response.json() == STUDENT_NOT_ENROLLED_BODY


def test_register_attendance_for_train_split_student_returns_422(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    db_session: Session,
) -> None:
    """AD-4/AD-11: `exists_enrollment` must apply the same `dataset_split =
    EVAL_DEMO` filter as `list_enrolled` — a `TRAIN`-split student who has a
    row in `enrollments` is never treated as validly enrolled for an
    attendance write."""
    train_student = StudentModel(name="Aluno de Treino", dataset_split=DatasetSplit.TRAIN)
    db_session.add(train_student)
    db_session.flush()
    db_session.add(EnrollmentModel(student_id=train_student.id, classroom_id=seeded_classroom.id))
    db_session.commit()

    response = client.post(
        "/attendance",
        json={
            "student_id": str(train_student.id),
            "classroom_id": str(seeded_classroom.id),
            "date": "2026-09-23",
            "status": "PRESENT",
        },
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422
    assert response.json() == STUDENT_NOT_ENROLLED_BODY


def test_register_attendance_for_unknown_classroom_returns_404(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
) -> None:
    """Mirrors `test_list_enrolled_students_for_unknown_classroom_returns_404`
    — a nonexistent `classroom_id` must be reported as `classroom_not_found`,
    not misdiagnosed as the student not being enrolled."""
    response = client.post(
        "/attendance",
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(uuid.uuid4()),
            "date": "2026-09-23",
            "status": "PRESENT",
        },
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 404
    assert response.json() == CLASSROOM_NOT_FOUND_BODY
