"""Covers every row of the spec's I/O & Edge-Case Matrix for `POST
/assignments`, `GET /classrooms/{classroom_id}/assignments`, and `POST
/assignment-submissions`."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.student import DatasetSplit
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    AssignmentModel,
    AssignmentSubmissionModel,
    ClassroomModel,
    EnrollmentModel,
    StudentModel,
)

CLASSROOM_NOT_FOUND_BODY = {
    "error": {"code": "classroom_not_found", "message": "Turma não encontrada."}
}
ACADEMIC_PERIOD_NOT_FOUND_BODY = {
    "error": {"code": "academic_period_not_found", "message": "Período letivo não encontrado."}
}
ASSIGNMENT_NOT_FOUND_BODY = {
    "error": {"code": "assignment_not_found", "message": "Atividade não encontrada."}
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


def _assignment_payload(
    classroom_id: uuid.UUID,
    period_id: uuid.UUID,
    subject: str = "Matemática",
    due_date: str = "2026-09-30",
) -> dict:
    return {
        "classroom_id": str(classroom_id),
        "subject": subject,
        "period_id": str(period_id),
        "due_date": due_date,
    }


def _submission_payload(
    assignment_id: uuid.UUID,
    student_id: uuid.UUID,
    status: str = "DELIVERED",
    date_: str = "2026-09-30",
) -> dict:
    return {
        "assignment_id": str(assignment_id),
        "student_id": str(student_id),
        "status": status,
        "date": date_,
    }


# --- Happy path — cadastro ----------------------------------------------------


def test_register_assignment_happy_path_returns_201_and_persists(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    response = client.post(
        "/assignments",
        json=_assignment_payload(seeded_classroom.id, seeded_academic_period.id),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["classroom_id"] == str(seeded_classroom.id)
    assert body["period_id"] == str(seeded_academic_period.id)
    assert body["subject"] == "Matemática"
    assert body["due_date"] == "2026-09-30"

    persisted = (
        db_session.query(AssignmentModel)
        .filter(AssignmentModel.classroom_id == seeded_classroom.id)
        .one()
    )
    assert persisted.subject == "Matemática"


def test_new_assignment_appears_in_the_classroom_assignment_list(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_academic_period: AcademicPeriodModel,
) -> None:
    headers = _auth_headers(client, seeded_user)
    created = client.post(
        "/assignments",
        json=_assignment_payload(seeded_classroom.id, seeded_academic_period.id),
        headers=headers,
    )
    assert created.status_code == 201
    assignment_id = created.json()["id"]

    listed = client.get(f"/classrooms/{seeded_classroom.id}/assignments", headers=headers)

    assert listed.status_code == 200
    assert assignment_id in [item["id"] for item in listed.json()]


# --- Happy path — status de entrega -------------------------------------------


def test_register_submission_happy_path_returns_201_and_persists(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_assignment: AssignmentModel,
    db_session: Session,
) -> None:
    response = client.post(
        "/assignment-submissions",
        json=_submission_payload(seeded_assignment.id, seeded_enrolled_student.id),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["assignment_id"] == str(seeded_assignment.id)
    assert body["student_id"] == str(seeded_enrolled_student.id)
    assert body["status"] == "DELIVERED"
    assert body["date"] == "2026-09-30"

    persisted = (
        db_session.query(AssignmentSubmissionModel)
        .filter(AssignmentSubmissionModel.student_id == seeded_enrolled_student.id)
        .one()
    )
    assert persisted.status.value == "DELIVERED"


def test_register_submission_allows_second_submission_same_assignment_student(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    seeded_assignment: AssignmentModel,
    db_session: Session,
) -> None:
    """Spec Boundaries & Constraints: `AssignmentSubmission` carries no
    UNIQUE constraint — a corrected/updated status is simply a new row,
    mirrors `Grade`'s already-accepted "no dedup" precedent."""
    headers = _auth_headers(client, seeded_user)
    payload = _submission_payload(seeded_assignment.id, seeded_enrolled_student.id)

    first = client.post("/assignment-submissions", json=payload, headers=headers)
    second = client.post(
        "/assignment-submissions",
        json={**payload, "status": "PARTIAL"},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    count = (
        db_session.query(AssignmentSubmissionModel)
        .filter(AssignmentSubmissionModel.student_id == seeded_enrolled_student.id)
        .count()
    )
    assert count == 2


# --- Unauthenticated -----------------------------------------------------------


def test_register_assignment_without_bearer_token_returns_401(
    client: TestClient,
    seeded_classroom: ClassroomModel,
    seeded_academic_period: AcademicPeriodModel,
) -> None:
    response = client.post(
        "/assignments", json=_assignment_payload(seeded_classroom.id, seeded_academic_period.id)
    )

    assert response.status_code == 401
    assert "error" in response.json()
    assert "detail" not in response.json()


def test_list_assignments_by_classroom_without_bearer_token_returns_401(
    client: TestClient, seeded_classroom: ClassroomModel
) -> None:
    response = client.get(f"/classrooms/{seeded_classroom.id}/assignments")

    assert response.status_code == 401
    assert "error" in response.json()


def test_register_submission_without_bearer_token_returns_401(
    client: TestClient, seeded_enrolled_student: StudentModel, seeded_assignment: AssignmentModel
) -> None:
    response = client.post(
        "/assignment-submissions",
        json=_submission_payload(seeded_assignment.id, seeded_enrolled_student.id),
    )

    assert response.status_code == 401
    assert "error" in response.json()


# --- Unknown classroom (assignment) -------------------------------------------


def test_register_assignment_for_unknown_classroom_returns_404(
    client: TestClient, seeded_user, seeded_academic_period: AcademicPeriodModel
) -> None:
    response = client.post(
        "/assignments",
        json=_assignment_payload(uuid.uuid4(), seeded_academic_period.id),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 404
    assert response.json() == CLASSROOM_NOT_FOUND_BODY


# --- Unknown period (assignment) ----------------------------------------------


def test_register_assignment_for_unknown_period_returns_404(
    client: TestClient, seeded_user, seeded_classroom: ClassroomModel
) -> None:
    response = client.post(
        "/assignments",
        json=_assignment_payload(seeded_classroom.id, uuid.uuid4()),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 404
    assert response.json() == ACADEMIC_PERIOD_NOT_FOUND_BODY


# --- Unknown classroom (list) --------------------------------------------------


def test_list_assignments_for_unknown_classroom_returns_404(
    client: TestClient, seeded_user
) -> None:
    response = client.get(
        f"/classrooms/{uuid.uuid4()}/assignments", headers=_auth_headers(client, seeded_user)
    )

    assert response.status_code == 404
    assert response.json() == CLASSROOM_NOT_FOUND_BODY


# --- Unknown assignment (submission) ------------------------------------------


def test_register_submission_for_unknown_assignment_returns_404(
    client: TestClient, seeded_user, seeded_enrolled_student: StudentModel
) -> None:
    response = client.post(
        "/assignment-submissions",
        json=_submission_payload(uuid.uuid4(), seeded_enrolled_student.id),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 404
    assert response.json() == ASSIGNMENT_NOT_FOUND_BODY


# --- Student not enrolled -------------------------------------------------------


def test_register_submission_for_student_not_enrolled_returns_422(
    client: TestClient,
    seeded_user,
    seeded_assignment: AssignmentModel,
    db_session: Session,
) -> None:
    unenrolled_student = StudentModel(name="Aluno Sem Matrícula", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add(unenrolled_student)
    db_session.commit()

    response = client.post(
        "/assignment-submissions",
        json=_submission_payload(seeded_assignment.id, unenrolled_student.id),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422
    assert response.json() == STUDENT_NOT_ENROLLED_BODY


def test_register_submission_for_train_split_student_returns_422(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_assignment: AssignmentModel,
    db_session: Session,
) -> None:
    """AD-4/AD-11: `exists_enrollment` must apply the same `dataset_split =
    EVAL_DEMO` filter used by attendance/grades — a `TRAIN`-split student who
    has a row in `enrollments` is never treated as validly enrolled for a
    submission write either."""
    train_student = StudentModel(name="Aluno de Treino", dataset_split=DatasetSplit.TRAIN)
    db_session.add(train_student)
    db_session.flush()
    db_session.add(EnrollmentModel(student_id=train_student.id, classroom_id=seeded_classroom.id))
    db_session.commit()

    response = client.post(
        "/assignment-submissions",
        json=_submission_payload(seeded_assignment.id, train_student.id),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422
    assert response.json() == STUDENT_NOT_ENROLLED_BODY


# --- Malformed status (API bypass) --------------------------------------------


def test_register_submission_with_malformed_status_returns_standard_422(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    seeded_assignment: AssignmentModel,
) -> None:
    response = client.post(
        "/assignment-submissions",
        json=_submission_payload(seeded_assignment.id, seeded_enrolled_student.id, status="FOO"),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422
    body = response.json()
    # Standard FastAPI/Pydantic validation body, not the `AppError` envelope.
    assert "detail" in body
    assert "error" not in body
