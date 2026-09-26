"""Covers every row of the spec's I/O & Edge-Case Matrix for `POST
/pedagogical-observations`."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.student import DatasetSplit
from app.infrastructure.db.models import (
    ClassroomModel,
    EnrollmentModel,
    PedagogicalObservationModel,
    StudentModel,
)

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


def _observation_payload(
    student_id: uuid.UUID,
    classroom_id: uuid.UUID,
    text: str = "Participou ativamente da aula e ajudou colegas.",
) -> dict:
    return {
        "student_id": str(student_id),
        "classroom_id": str(classroom_id),
        "text": text,
    }


# --- Happy path -------------------------------------------------------------


def test_register_observation_happy_path_returns_201_and_persists(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
) -> None:
    before = datetime.now(timezone.utc)
    response = client.post(
        "/pedagogical-observations",
        json=_observation_payload(seeded_enrolled_student.id, seeded_classroom.id),
        headers=_auth_headers(client, seeded_user),
    )
    after = datetime.now(timezone.utc)

    assert response.status_code == 201
    body = response.json()
    assert body["student_id"] == str(seeded_enrolled_student.id)
    # author_user_id comes from the bearer token's `sub` claim, never the
    # request body (spec Boundaries & Constraints) — there is no
    # `author_user_id` field in the request at all.
    assert body["author_user_id"] == str(seeded_user.id)
    assert body["text"] == "Participou ativamente da aula e ajudou colegas."
    # classroom_id is validation-only — never part of the persisted shape or
    # the response (spec Design Notes / data-model.md's fixed shape).
    assert "classroom_id" not in body

    persisted = (
        db_session.query(PedagogicalObservationModel)
        .filter(PedagogicalObservationModel.student_id == seeded_enrolled_student.id)
        .one()
    )
    assert persisted.author_user_id == seeded_user.id
    assert persisted.text == "Participou ativamente da aula e ajudou colegas."
    assert before <= persisted.created_at <= after


def test_register_observation_allows_second_observation_same_student(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
) -> None:
    """Spec Boundaries & Constraints / UX-DR13: "toda ação registrada entra
    no histórico, nunca substitui uma anterior" — no UNIQUE constraint, no
    duplicate-observation rejection; multiple observations for the same
    student are expected and valid, each a new row."""
    headers = _auth_headers(client, seeded_user)
    payload = _observation_payload(seeded_enrolled_student.id, seeded_classroom.id)

    first = client.post("/pedagogical-observations", json=payload, headers=headers)
    second = client.post("/pedagogical-observations", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    count = (
        db_session.query(PedagogicalObservationModel)
        .filter(PedagogicalObservationModel.student_id == seeded_enrolled_student.id)
        .count()
    )
    assert count == 2


# --- Whitespace-only / blank text (API bypass) -------------------------------


def test_register_observation_whitespace_only_text_returns_standard_422(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    response = client.post(
        "/pedagogical-observations",
        json=_observation_payload(seeded_enrolled_student.id, seeded_classroom.id, text="   "),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422
    body = response.json()
    # Standard FastAPI/Pydantic validation body (`min_length=1` after
    # `strip_whitespace=True`), not the `AppError` envelope.
    assert "detail" in body
    assert "error" not in body


def test_register_observation_blank_text_returns_standard_422(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    response = client.post(
        "/pedagogical-observations",
        json=_observation_payload(seeded_enrolled_student.id, seeded_classroom.id, text=""),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    assert "error" not in body


# --- Unauthenticated -----------------------------------------------------------


def test_register_observation_without_bearer_token_returns_401(
    client: TestClient,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    response = client.post(
        "/pedagogical-observations",
        json=_observation_payload(seeded_enrolled_student.id, seeded_classroom.id),
    )

    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert "detail" not in body


# --- Unknown classroom ---------------------------------------------------------


def test_register_observation_for_unknown_classroom_returns_404(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
) -> None:
    response = client.post(
        "/pedagogical-observations",
        json=_observation_payload(seeded_enrolled_student.id, uuid.uuid4()),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 404
    assert response.json() == CLASSROOM_NOT_FOUND_BODY


# --- Student not enrolled -------------------------------------------------------


def test_register_observation_for_student_not_enrolled_returns_422(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    db_session: Session,
) -> None:
    other_classroom = ClassroomModel(name="Outra Turma", academic_year=2026)
    db_session.add(other_classroom)
    db_session.flush()
    unenrolled_student = StudentModel(
        name="Aluno Sem Matrícula", dataset_split=DatasetSplit.EVAL_DEMO
    )
    db_session.add(unenrolled_student)
    db_session.commit()

    response = client.post(
        "/pedagogical-observations",
        json=_observation_payload(unenrolled_student.id, seeded_classroom.id),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422
    assert response.json() == STUDENT_NOT_ENROLLED_BODY


def test_register_observation_for_train_split_student_returns_422(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    db_session: Session,
) -> None:
    """AD-4/AD-11: `exists_enrollment` must apply the same `dataset_split =
    EVAL_DEMO` filter used by attendance/grades — a `TRAIN`-split student who
    has a row in `enrollments` is never treated as validly enrolled for an
    observation write either."""
    train_student = StudentModel(name="Aluno de Treino", dataset_split=DatasetSplit.TRAIN)
    db_session.add(train_student)
    db_session.flush()
    db_session.add(EnrollmentModel(student_id=train_student.id, classroom_id=seeded_classroom.id))
    db_session.commit()

    response = client.post(
        "/pedagogical-observations",
        json=_observation_payload(train_student.id, seeded_classroom.id),
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 422
    assert response.json() == STUDENT_NOT_ENROLLED_BODY
