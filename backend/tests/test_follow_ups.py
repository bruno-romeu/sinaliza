"""Covers the spec's I/O & Edge-Case Matrix for `POST /follow-ups` and
`GET /follow-ups/{id}` (Story 4.1), plus the freeze-on-evidence guard
deferred from Story 3.2 onto `sqlalchemy_trajectory_change_repository.py`'s
upsert."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.student import DatasetSplit
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    AttendanceRecordModel,
    ClassroomModel,
    PedagogicalObservationModel,
    StudentModel,
    TrajectoryChangeSourceModel,
)

TRAJECTORY_CHANGE_NOT_FOUND_BODY = {
    "error": {
        "code": "trajectory_change_not_found",
        "message": "Mudança de trajetória não encontrada.",
    }
}
FOLLOW_UP_NOT_FOUND_BODY = {
    "error": {"code": "follow_up_not_found", "message": "Acompanhamento não encontrado."}
}
INVALID_TOKEN_BODY = {
    "error": {"code": "invalid_token", "message": "Sessão expirada ou inválida."}
}

# Falls inside `seeded_academic_period`'s window (2026-07-27 .. 2026-09-25).
AS_OF = "2026-09-24"


@pytest.fixture(autouse=True)
def _frozen_as_of(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", AS_OF)


def _auth_headers(client: TestClient, seeded_user) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": seeded_user.email, "password": "Senha-Correta-123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _detect_attendance_drop_change(
    client: TestClient,
    headers: dict[str, str],
    db_session: Session,
    student: StudentModel,
    classroom: ClassroomModel,
    author_user_id: uuid.UUID,
) -> dict:
    """Seeds ATTENDANCE + PEDAGOGICAL_OBSERVATION confirmed signals, then
    calls the detail endpoint (which upserts the `TrajectoryChange` as a side
    effect, Story 3.2/3.4's existing flow) and returns its
    `trajectory_change` dict, including the Story 4.1 additive `id`."""
    day = date(2026, 8, 1)
    for _ in range(1):
        db_session.add(
            AttendanceRecordModel(
                student_id=student.id,
                classroom_id=classroom.id,
                date=day,
                status="PRESENT",
            )
        )
    for i in range(2):
        db_session.add(
            AttendanceRecordModel(
                student_id=student.id,
                classroom_id=classroom.id,
                date=date(2026, 8, 2 + i),
                status="ABSENT_UNJUSTIFIED",
            )
        )
    db_session.add(
        PedagogicalObservationModel(
            student_id=student.id,
            author_user_id=author_user_id,
            text="Observação de teste.",
            created_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    response = client.get(f"/students/{student.id}/trajectory/detail", headers=headers)
    assert response.status_code == 200
    change = response.json()["trajectory_change"]
    assert change is not None
    assert change["type"] == "ATTENDANCE_DROP"
    return change


# --- Open follow-up: happy path ------------------------------------------------------


def test_open_follow_up_creates_follow_up_and_evidence_then_fetch_returns_detail(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    headers = _auth_headers(client, seeded_user)
    change = _detect_attendance_drop_change(
        client, headers, db_session, seeded_enrolled_student, seeded_classroom, seeded_user.id
    )

    open_response = client.post(
        "/follow-ups",
        json={
            "student_id": str(seeded_enrolled_student.id),
            "trajectory_change_id": change["id"],
        },
        headers=headers,
    )

    assert open_response.status_code == 201
    body = open_response.json()
    assert body["student_id"] == str(seeded_enrolled_student.id)
    assert body["status"] == "EM_OBSERVACAO"
    assert body["created_at"]
    follow_up_id = body["id"]

    get_response = client.get(f"/follow-ups/{follow_up_id}", headers=headers)
    assert get_response.status_code == 200
    detail = get_response.json()
    assert detail["id"] == follow_up_id
    assert detail["student_id"] == str(seeded_enrolled_student.id)
    assert detail["student_name"] == seeded_enrolled_student.name
    assert detail["status"] == "EM_OBSERVACAO"
    # Same evidence resolution path as the trajectory detail endpoint
    # (RNF-11: every item traces to a real source record).
    assert len(detail["evidence"]) >= 1
    source_types = {item["source_type"] for item in detail["evidence"]}
    assert "ATTENDANCE_RECORD" in source_types or "PEDAGOGICAL_OBSERVATION" in source_types
    for item in detail["evidence"]:
        assert item["description"]
        assert item["date"]


# --- Unknown trajectory_change_id ----------------------------------------------------


def test_open_follow_up_with_unknown_trajectory_change_id_returns_404(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
) -> None:
    headers = _auth_headers(client, seeded_user)

    response = client.post(
        "/follow-ups",
        json={
            "student_id": str(seeded_enrolled_student.id),
            "trajectory_change_id": str(uuid.uuid4()),
        },
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json() == TRAJECTORY_CHANGE_NOT_FOUND_BODY


# --- student_id/trajectory_change mismatch -------------------------------------------


def test_open_follow_up_with_mismatched_student_returns_422(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    headers = _auth_headers(client, seeded_user)
    change = _detect_attendance_drop_change(
        client, headers, db_session, seeded_enrolled_student, seeded_classroom, seeded_user.id
    )

    other_student = StudentModel(name="Outro Estudante", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add(other_student)
    db_session.commit()

    response = client.post(
        "/follow-ups",
        json={"student_id": str(other_student.id), "trajectory_change_id": change["id"]},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "trajectory_change_mismatch",
            "message": "A mudança de trajetória não pertence a este estudante.",
        }
    }


# --- Freeze-on-evidence guard ----------------------------------------------------------


def test_recompute_after_follow_up_evidence_exists_keeps_change_frozen(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    headers = _auth_headers(client, seeded_user)
    change = _detect_attendance_drop_change(
        client, headers, db_session, seeded_enrolled_student, seeded_classroom, seeded_user.id
    )
    original_description = change["description"]
    original_detected_at = change["detected_at"]

    open_response = client.post(
        "/follow-ups",
        json={
            "student_id": str(seeded_enrolled_student.id),
            "trajectory_change_id": change["id"],
        },
        headers=headers,
    )
    assert open_response.status_code == 201

    source_ids_before = {
        row.id
        for row in db_session.query(TrajectoryChangeSourceModel)
        .filter(TrajectoryChangeSourceModel.trajectory_change_id == change["id"])
        .all()
    }
    assert source_ids_before

    # Recompute the same período with materially different attendance data —
    # without the freeze guard this would upsert a new description/detected_at
    # and replace the TrajectoryChangeSource rows.
    db_session.add(
        AttendanceRecordModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            date=date(2026, 9, 10),
            status="ABSENT_UNJUSTIFIED",
        )
    )
    db_session.add(
        PedagogicalObservationModel(
            student_id=seeded_enrolled_student.id,
            author_user_id=seeded_user.id,
            text="Nova observação pós-congelamento.",
            created_at=datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    recompute_response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail", headers=headers
    )
    assert recompute_response.status_code == 200
    recomputed_change = recompute_response.json()["trajectory_change"]

    assert recomputed_change["id"] == change["id"]
    assert recomputed_change["description"] == original_description
    assert recomputed_change["detected_at"] == original_detected_at

    # The TrajectoryChangeSource rows themselves were never touched — not
    # even delete+reinsert of the identical set — proving the freeze guard
    # skips the whole sources-replacement step, not just the visible fields.
    db_session.expire_all()
    source_ids_after = {
        row.id
        for row in db_session.query(TrajectoryChangeSourceModel)
        .filter(TrajectoryChangeSourceModel.trajectory_change_id == change["id"])
        .all()
    }
    assert source_ids_after == source_ids_before

    # The evidence behind the now-frozen change is unchanged too — the new
    # observation/attendance record above must not appear.
    follow_up_detail = client.get(
        f"/follow-ups/{open_response.json()['id']}", headers=headers
    ).json()
    descriptions = {item["description"] for item in follow_up_detail["evidence"]}
    assert "Nova observação pós-congelamento." not in "".join(descriptions)


# --- Get follow-up: nonexistent --------------------------------------------------------


def test_get_follow_up_for_unknown_id_returns_404(client: TestClient, seeded_user) -> None:
    headers = _auth_headers(client, seeded_user)

    response = client.get(f"/follow-ups/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404
    assert response.json() == FOLLOW_UP_NOT_FOUND_BODY


# --- Unauthenticated ---------------------------------------------------------------------


def test_open_follow_up_without_bearer_token_returns_401(
    client: TestClient, seeded_enrolled_student: StudentModel
) -> None:
    response = client.post(
        "/follow-ups",
        json={
            "student_id": str(seeded_enrolled_student.id),
            "trajectory_change_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 401
    assert response.json() == INVALID_TOKEN_BODY


def test_get_follow_up_without_bearer_token_returns_401(client: TestClient) -> None:
    response = client.get(f"/follow-ups/{uuid.uuid4()}")

    assert response.status_code == 401
    assert response.json() == INVALID_TOKEN_BODY
