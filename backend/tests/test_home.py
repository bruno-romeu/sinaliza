"""Covers every row of spec-3-3's I/O & Edge-Case Matrix for `GET /home` and
`GET /home/search`."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.student import DatasetSplit
from app.domain.trajectory_change import TrajectoryChangeType
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    ClassroomModel,
    EnrollmentModel,
    StudentModel,
    TrajectoryChangeModel,
)


def _auth_headers(client: TestClient, seeded_user) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": seeded_user.email, "password": "Senha-Correta-123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _add_change(
    db_session: Session,
    student: StudentModel,
    period: AcademicPeriodModel,
    detected_at: datetime,
    change_type: TrajectoryChangeType = TrajectoryChangeType.ATTENDANCE_DROP,
) -> TrajectoryChangeModel:
    change = TrajectoryChangeModel(
        student_id=student.id,
        type=change_type,
        period_id=period.id,
        detected_at=detected_at,
        description=f"Mudança recente: teste — {period.label}",
    )
    db_session.add(change)
    return change


# --- Recent changes exist -----------------------------------------------------------


def test_home_returns_recent_changes_ordered_by_detected_at_desc(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    older_student = StudentModel(name="Estudante Antigo", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add(older_student)
    db_session.flush()

    _add_change(
        db_session,
        seeded_enrolled_student,
        seeded_academic_period,
        datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc),
        TrajectoryChangeType.ATTENDANCE_DROP,
    )
    _add_change(
        db_session,
        older_student,
        seeded_academic_period,
        datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc),
        TrajectoryChangeType.GRADE_DROP,
    )
    db_session.commit()

    response = client.get("/home", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    body = response.json()
    assert [row["student_name"] for row in body["recent_changes"]] == [
        "Estudante Teste",
        "Estudante Antigo",
    ]
    assert body["recent_changes"][0]["type"] == "ATTENDANCE_DROP"
    assert body["recent_changes"][0]["student_id"] == str(seeded_enrolled_student.id)


# --- No recent changes --------------------------------------------------------------


def test_home_with_no_trajectory_changes_returns_empty_list(
    client: TestClient, seeded_user
) -> None:
    response = client.get("/home", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    assert response.json() == {"recent_changes": []}


# --- Caps at 20 -----------------------------------------------------------------------


def test_home_caps_recent_changes_at_twenty(
    client: TestClient,
    seeded_user,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    base_time = datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc)
    for i in range(25):
        student = StudentModel(name=f"Estudante {i:02d}", dataset_split=DatasetSplit.EVAL_DEMO)
        db_session.add(student)
        db_session.flush()
        _add_change(
            db_session,
            student,
            seeded_academic_period,
            base_time - timedelta(days=i),
        )
    db_session.commit()

    response = client.get("/home", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    recent_changes = response.json()["recent_changes"]
    assert len(recent_changes) == 20
    # The 20 most recent — i.e. the smallest `i` values (0..19) — not the
    # first 20 inserted.
    assert recent_changes[0]["student_name"] == "Estudante 00"
    assert recent_changes[-1]["student_name"] == "Estudante 19"


# --- Search matches -------------------------------------------------------------------


def test_home_search_matches_student_name(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    seeded_classroom: ClassroomModel,
) -> None:
    response = client.get(
        "/home/search?q=Estudante",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"] == [
        {
            "id": str(seeded_enrolled_student.id),
            "name": "Estudante Teste",
            "classroom_name": "Turma Teste",
        }
    ]


def test_home_search_matches_classroom_name(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    seeded_classroom: ClassroomModel,
) -> None:
    response = client.get(
        "/home/search?q=turma teste",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["name"] == "Estudante Teste"


def test_home_search_excludes_train_split_students(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    db_session: Session,
) -> None:
    train_student = StudentModel(name="Aluno de Treino", dataset_split=DatasetSplit.TRAIN)
    db_session.add(train_student)
    db_session.flush()
    db_session.add(EnrollmentModel(student_id=train_student.id, classroom_id=seeded_classroom.id))
    db_session.commit()

    response = client.get(
        "/home/search?q=Treino",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    assert response.json() == {"results": [], "count": 0}


# --- Search no match -------------------------------------------------------------------


def test_home_search_no_match_returns_empty_results(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
) -> None:
    response = client.get(
        "/home/search?q=NomeInexistente",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    assert response.json() == {"results": [], "count": 0}


# --- Unauthenticated ---------------------------------------------------------------------


def test_home_without_bearer_token_returns_401(client: TestClient) -> None:
    response = client.get("/home")

    assert response.status_code == 401
    assert "error" in response.json()


def test_home_search_without_bearer_token_returns_401(client: TestClient) -> None:
    response = client.get("/home/search?q=qualquer")

    assert response.status_code == 401
    assert "error" in response.json()
