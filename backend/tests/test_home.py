"""Covers every row of spec-3-3's I/O & Edge-Case Matrix for `GET /home` and
`GET /home/search`."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.follow_up import FollowUpStatus
from app.domain.student import DatasetSplit
from app.domain.trajectory_change import TrajectoryChangeType
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    ClassroomModel,
    EnrollmentModel,
    FollowUpModel,
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


def _add_follow_up(
    db_session: Session,
    student: StudentModel,
    responsible_user_id: uuid.UUID,
    status: FollowUpStatus,
    created_at: datetime,
) -> FollowUpModel:
    follow_up = FollowUpModel(
        student_id=student.id,
        status=status,
        reason=None,
        responsible_user_id=responsible_user_id,
        next_review_date=None,
        created_at=created_at,
    )
    db_session.add(follow_up)
    return follow_up


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
    assert response.json() == {
        "recent_changes": [],
        "in_progress_follow_ups": [],
        "in_progress_follow_ups_total": 0,
        "in_progress_follow_ups_page": 1,
        "in_progress_follow_ups_page_size": 20,
    }


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


# --- id.desc() tiebreaker ------------------------------------------------------------


def test_home_breaks_detected_at_tie_by_id_desc(
    client: TestClient,
    seeded_user,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    """Two `TrajectoryChange` rows computed under the same demo "today" share
    an identical `detected_at` (Story 3.2's `as_of()` date). Without a
    deterministic secondary `ORDER BY` key, which row sorts first is
    undefined by SQL (Review Triage Log, Pass 1 finding #1) — this pins the
    `TrajectoryChangeModel.id.desc()` tiebreaker."""
    student_low = StudentModel(name="Estudante Baixo", dataset_split=DatasetSplit.EVAL_DEMO)
    student_high = StudentModel(name="Estudante Alto", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add_all([student_low, student_high])
    db_session.flush()

    same_detected_at = datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc)
    change_low = TrajectoryChangeModel(
        id=uuid.UUID(int=1),
        student_id=student_low.id,
        type=TrajectoryChangeType.ATTENDANCE_DROP,
        period_id=seeded_academic_period.id,
        detected_at=same_detected_at,
        description="Mudança recente: teste — baixo",
    )
    change_high = TrajectoryChangeModel(
        id=uuid.UUID(int=2),
        student_id=student_high.id,
        type=TrajectoryChangeType.ATTENDANCE_DROP,
        period_id=seeded_academic_period.id,
        detected_at=same_detected_at,
        description="Mudança recente: teste — alto",
    )
    db_session.add_all([change_low, change_high])
    db_session.commit()

    response = client.get("/home", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    student_names = [row["student_name"] for row in response.json()["recent_changes"]]
    # Identical `detected_at` -> the higher `id` (change_high) must sort
    # first, deterministically, every time.
    assert student_names == ["Estudante Alto", "Estudante Baixo"]


# --- Active follow-ups (spec-4-5) -----------------------------------------------------


def test_home_includes_active_follow_ups_ordered_by_created_at_desc(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
) -> None:
    older_student = StudentModel(name="Estudante Antigo FU", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add(older_student)
    db_session.flush()

    _add_follow_up(
        db_session,
        seeded_enrolled_student,
        seeded_user.id,
        FollowUpStatus.EM_OBSERVACAO,
        datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc),
    )
    _add_follow_up(
        db_session,
        older_student,
        seeded_user.id,
        FollowUpStatus.ACOMPANHAMENTO_ATIVO,
        datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    response = client.get("/home", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    body = response.json()
    assert [row["student_name"] for row in body["in_progress_follow_ups"]] == [
        "Estudante Teste",
        "Estudante Antigo FU",
    ]
    assert body["in_progress_follow_ups"][0]["status"] == "EM_OBSERVACAO"
    assert body["in_progress_follow_ups"][0]["student_id"] == str(seeded_enrolled_student.id)


def test_home_breaks_follow_up_created_at_tie_by_id_desc(
    client: TestClient,
    seeded_user,
    db_session: Session,
) -> None:
    """Two active `FollowUp` rows sharing an identical `created_at` must still
    sort deterministically — mirrors
    `test_home_breaks_detected_at_tie_by_id_desc` for `list_active()`'s own
    `created_at.desc(), id.desc()` tiebreak (spec-4-5 Code Map)."""
    student_low = StudentModel(name="Estudante FU Baixo", dataset_split=DatasetSplit.EVAL_DEMO)
    student_high = StudentModel(name="Estudante FU Alto", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add_all([student_low, student_high])
    db_session.flush()

    same_created_at = datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc)
    follow_up_low = FollowUpModel(
        id=uuid.UUID(int=1),
        student_id=student_low.id,
        status=FollowUpStatus.EM_OBSERVACAO,
        reason=None,
        responsible_user_id=seeded_user.id,
        next_review_date=None,
        created_at=same_created_at,
    )
    follow_up_high = FollowUpModel(
        id=uuid.UUID(int=2),
        student_id=student_high.id,
        status=FollowUpStatus.EM_OBSERVACAO,
        reason=None,
        responsible_user_id=seeded_user.id,
        next_review_date=None,
        created_at=same_created_at,
    )
    db_session.add_all([follow_up_low, follow_up_high])
    db_session.commit()

    response = client.get("/home", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    student_names = [row["student_name"] for row in response.json()["in_progress_follow_ups"]]
    # Identical `created_at` -> the higher `id` (follow_up_high) must sort
    # first, deterministically, every time.
    assert student_names == ["Estudante FU Alto", "Estudante FU Baixo"]


def test_home_paginates_active_follow_ups_at_twenty_per_page_by_default(
    client: TestClient,
    seeded_user,
    db_session: Session,
) -> None:
    """Open-case volume grows without bound over a real deployment's
    lifetime, so `list_active` is paginated (20 per page by default) rather
    than returned whole — pins that 25 seeded active follow-ups come back as
    a 20-item first page plus an accurate `total`."""
    base_time = datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc)
    for i in range(25):
        student = StudentModel(name=f"Estudante FU {i:02d}", dataset_split=DatasetSplit.EVAL_DEMO)
        db_session.add(student)
        db_session.flush()
        _add_follow_up(
            db_session,
            student,
            seeded_user.id,
            FollowUpStatus.EM_OBSERVACAO,
            base_time - timedelta(days=i),
        )
    db_session.commit()

    response = client.get("/home", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    body = response.json()
    assert len(body["in_progress_follow_ups"]) == 20
    assert body["in_progress_follow_ups_total"] == 25
    assert body["in_progress_follow_ups_page"] == 1
    assert body["in_progress_follow_ups_page_size"] == 20


def test_home_follow_ups_second_page_returns_the_remainder(
    client: TestClient,
    seeded_user,
    db_session: Session,
) -> None:
    base_time = datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc)
    for i in range(25):
        student = StudentModel(name=f"Estudante FU {i:02d}", dataset_split=DatasetSplit.EVAL_DEMO)
        db_session.add(student)
        db_session.flush()
        _add_follow_up(
            db_session,
            student,
            seeded_user.id,
            FollowUpStatus.EM_OBSERVACAO,
            base_time - timedelta(days=i),
        )
    db_session.commit()

    response = client.get(
        "/home?follow_ups_page=2", headers=_auth_headers(client, seeded_user)
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["in_progress_follow_ups"]) == 5
    assert body["in_progress_follow_ups_total"] == 25
    assert body["in_progress_follow_ups_page"] == 2
    # The oldest 5 (days 20..24 ago) — page 1 already returned the 20 newest.
    assert [row["student_name"] for row in body["in_progress_follow_ups"]] == [
        f"Estudante FU {i:02d}" for i in range(20, 25)
    ]


def test_home_follow_ups_page_size_query_param_overrides_default(
    client: TestClient,
    seeded_user,
    db_session: Session,
) -> None:
    base_time = datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc)
    for i in range(5):
        student = StudentModel(name=f"Estudante FU {i:02d}", dataset_split=DatasetSplit.EVAL_DEMO)
        db_session.add(student)
        db_session.flush()
        _add_follow_up(
            db_session,
            student,
            seeded_user.id,
            FollowUpStatus.EM_OBSERVACAO,
            base_time - timedelta(days=i),
        )
    db_session.commit()

    response = client.get(
        "/home?follow_ups_page_size=2", headers=_auth_headers(client, seeded_user)
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["in_progress_follow_ups"]) == 2
    assert body["in_progress_follow_ups_total"] == 5
    assert body["in_progress_follow_ups_page_size"] == 2


def test_home_excludes_encerrado_follow_ups(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
) -> None:
    active_student = StudentModel(name="Estudante Ativo", dataset_split=DatasetSplit.EVAL_DEMO)
    closed_student = StudentModel(name="Estudante Encerrado", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add_all([active_student, closed_student])
    db_session.flush()

    now = datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc)
    _add_follow_up(db_session, active_student, seeded_user.id, FollowUpStatus.AGUARDANDO_RETORNO, now)
    _add_follow_up(db_session, closed_student, seeded_user.id, FollowUpStatus.ENCERRADO, now)
    db_session.commit()

    response = client.get("/home", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    body = response.json()
    student_names = [row["student_name"] for row in body["in_progress_follow_ups"]]
    assert student_names == ["Estudante Ativo"]


def test_home_with_no_active_follow_ups_returns_empty_list(
    client: TestClient, seeded_user
) -> None:
    response = client.get("/home", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    assert response.json()["in_progress_follow_ups"] == []


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
    assert response.json() == {"results": [], "count": 0, "total": 0, "page": 1, "page_size": 20}


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
    assert response.json() == {"results": [], "count": 0, "total": 0, "page": 1, "page_size": 20}


# --- Blank/whitespace q short-circuit (HTTP boundary) ----------------------------------


def test_home_search_blank_q_returns_empty_results(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
) -> None:
    """`SearchStudentsService.execute()` short-circuits a blank/whitespace-only
    `q` to an empty result before ever reaching the `ILIKE '%%'` match
    (Review Triage Log, Pass 1 finding #3) — exercised here at the HTTP
    boundary, not just via the frontend's own never-calls-blank guard."""
    response = client.get("/home/search?q=", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    assert response.json() == {"results": [], "count": 0, "total": 0, "page": 1, "page_size": 20}


def test_home_search_whitespace_only_q_returns_empty_results(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
) -> None:
    response = client.get("/home/search?q=%20%20%20", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    assert response.json() == {"results": [], "count": 0, "total": 0, "page": 1, "page_size": 20}


# --- %/_ escaping in the ILIKE pattern ---------------------------------------------------


def test_home_search_escapes_percent_wildcard(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    db_session: Session,
) -> None:
    """A literal `%` in the query must be matched literally, not treated as
    the SQL `ILIKE` wildcard (Review Triage Log, Pass 1 finding #2)."""
    student = StudentModel(name="100% Aprovado", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add(student)
    db_session.flush()
    db_session.add(EnrollmentModel(student_id=student.id, classroom_id=seeded_classroom.id))
    db_session.commit()

    response = client.get("/home/search?q=100%25", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["name"] == "100% Aprovado"


def test_home_search_escapes_underscore_wildcard(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    db_session: Session,
) -> None:
    """A literal `_` in the query must be matched literally, not treated as
    the SQL `ILIKE` single-character wildcard (Review Triage Log, Pass 1
    finding #2) — `"A_a"` must not also match an unrelated name like
    `"Ana"`."""
    target = StudentModel(name="A_a", dataset_split=DatasetSplit.EVAL_DEMO)
    decoy = StudentModel(name="Ana", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add_all([target, decoy])
    db_session.flush()
    db_session.add_all(
        [
            EnrollmentModel(student_id=target.id, classroom_id=seeded_classroom.id),
            EnrollmentModel(student_id=decoy.id, classroom_id=seeded_classroom.id),
        ]
    )
    db_session.commit()

    response = client.get("/home/search?q=A_a", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["name"] == "A_a"


# --- Search pagination -----------------------------------------------------------------


def test_home_search_paginates_at_twenty_per_page_by_default(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    db_session: Session,
) -> None:
    """`GET /home/search` pages at 20 per page by default — `total` reports
    every match, not just this page's length, so a caller can page through
    the rest instead of it silently vanishing past the cap."""
    for i in range(25):
        student = StudentModel(name=f"Busca {i:02d}", dataset_split=DatasetSplit.EVAL_DEMO)
        db_session.add(student)
        db_session.flush()
        db_session.add(EnrollmentModel(student_id=student.id, classroom_id=seeded_classroom.id))
    db_session.commit()

    response = client.get("/home/search?q=Busca", headers=_auth_headers(client, seeded_user))

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 20
    assert len(body["results"]) == 20
    assert body["total"] == 25
    assert body["page"] == 1
    assert body["page_size"] == 20


def test_home_search_second_page_returns_the_remainder(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    db_session: Session,
) -> None:
    for i in range(25):
        student = StudentModel(name=f"Busca {i:02d}", dataset_split=DatasetSplit.EVAL_DEMO)
        db_session.add(student)
        db_session.flush()
        db_session.add(EnrollmentModel(student_id=student.id, classroom_id=seeded_classroom.id))
    db_session.commit()

    response = client.get(
        "/home/search?q=Busca&page=2", headers=_auth_headers(client, seeded_user)
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 5
    assert body["total"] == 25
    assert body["page"] == 2
    # Ordered by name, so page 1 took "Busca 00".."Busca 19" alphabetically.
    assert [r["name"] for r in body["results"]] == [f"Busca {i:02d}" for i in range(20, 25)]


def test_home_search_page_size_query_param_overrides_default(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    db_session: Session,
) -> None:
    for i in range(5):
        student = StudentModel(name=f"Busca {i:02d}", dataset_split=DatasetSplit.EVAL_DEMO)
        db_session.add(student)
        db_session.flush()
        db_session.add(EnrollmentModel(student_id=student.id, classroom_id=seeded_classroom.id))
    db_session.commit()

    response = client.get(
        "/home/search?q=Busca&page_size=2", headers=_auth_headers(client, seeded_user)
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 2
    assert body["total"] == 5
    assert body["page_size"] == 2


# --- Unauthenticated ---------------------------------------------------------------------


def test_home_without_bearer_token_returns_401(client: TestClient) -> None:
    response = client.get("/home")

    assert response.status_code == 401
    assert "error" in response.json()


def test_home_search_without_bearer_token_returns_401(client: TestClient) -> None:
    response = client.get("/home/search?q=qualquer")

    assert response.status_code == 401
    assert "error" in response.json()
