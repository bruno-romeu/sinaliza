"""Covers the spec's I/O & Edge-Case Matrix for `POST /follow-ups` and
`GET /follow-ups/{id}` (Story 4.1), plus the freeze-on-evidence guard
deferred from Story 3.2 onto `sqlalchemy_trajectory_change_repository.py`'s
upsert."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.student import DatasetSplit
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    AttendanceRecordModel,
    ClassroomModel,
    FollowUpActionModel,
    FollowUpModel,
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


# --- Story 4.2: register action / change status ----------------------------------------


def _seed_follow_up(
    db_session: Session, student: StudentModel, responsible_user_id: uuid.UUID
) -> FollowUpModel:
    """Inserts a `FollowUp` row directly — this story's action/status tests
    don't need a real `TrajectoryChange`/evidence trail, just an existing
    follow-up to act on."""
    follow_up = FollowUpModel(
        id=uuid.uuid4(),
        student_id=student.id,
        status="EM_OBSERVACAO",
        reason=None,
        responsible_user_id=responsible_user_id,
        next_review_date=None,
        created_at=datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc),
    )
    db_session.add(follow_up)
    db_session.commit()
    db_session.refresh(follow_up)
    return follow_up


def test_register_follow_up_action_persists_and_appends(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
) -> None:
    headers = _auth_headers(client, seeded_user)
    follow_up = _seed_follow_up(db_session, seeded_enrolled_student, seeded_user.id)

    first = client.post(
        f"/follow-ups/{follow_up.id}/actions",
        json={"description": "Primeira ação registrada."},
        headers=headers,
    )
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["follow_up_id"] == str(follow_up.id)
    assert first_body["description"] == "Primeira ação registrada."
    assert first_body["author_user_id"] == str(seeded_user.id)
    assert first_body["created_at"]

    second = client.post(
        f"/follow-ups/{follow_up.id}/actions",
        json={"description": "Segunda ação registrada."},
        headers=headers,
    )
    assert second.status_code == 201
    assert second.json()["id"] != first_body["id"]

    rows = (
        db_session.query(FollowUpActionModel)
        .filter(FollowUpActionModel.follow_up_id == follow_up.id)
        .all()
    )
    assert len(rows) == 2
    descriptions = {row.description for row in rows}
    assert descriptions == {"Primeira ação registrada.", "Segunda ação registrada."}


def test_register_follow_up_action_with_blank_description_returns_422(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
) -> None:
    headers = _auth_headers(client, seeded_user)
    follow_up = _seed_follow_up(db_session, seeded_enrolled_student, seeded_user.id)

    response = client.post(
        f"/follow-ups/{follow_up.id}/actions",
        json={"description": "   "},
        headers=headers,
    )

    assert response.status_code == 422


def test_register_follow_up_action_on_unknown_follow_up_returns_404(
    client: TestClient, seeded_user
) -> None:
    headers = _auth_headers(client, seeded_user)

    response = client.post(
        f"/follow-ups/{uuid.uuid4()}/actions",
        json={"description": "Ação qualquer."},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json() == FOLLOW_UP_NOT_FOUND_BODY


@pytest.mark.parametrize(
    "target_status",
    ["EM_OBSERVACAO", "ACOMPANHAMENTO_ATIVO", "AGUARDANDO_RETORNO", "ENCERRADO"],
)
def test_change_follow_up_status_happy_path(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
    target_status: str,
) -> None:
    headers = _auth_headers(client, seeded_user)
    follow_up = _seed_follow_up(db_session, seeded_enrolled_student, seeded_user.id)

    response = client.patch(
        f"/follow-ups/{follow_up.id}/status",
        json={"status": target_status},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(follow_up.id)
    assert body["status"] == target_status

    db_session.expire_all()
    refreshed = db_session.get(FollowUpModel, follow_up.id)
    assert refreshed.status.value == target_status


def test_change_follow_up_status_on_unknown_follow_up_returns_404(
    client: TestClient, seeded_user
) -> None:
    headers = _auth_headers(client, seeded_user)

    response = client.patch(
        f"/follow-ups/{uuid.uuid4()}/status",
        json={"status": "ENCERRADO"},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json() == FOLLOW_UP_NOT_FOUND_BODY


def test_change_follow_up_status_with_invalid_status_returns_422(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
) -> None:
    headers = _auth_headers(client, seeded_user)
    follow_up = _seed_follow_up(db_session, seeded_enrolled_student, seeded_user.id)

    response = client.patch(
        f"/follow-ups/{follow_up.id}/status",
        json={"status": "FOO"},
        headers=headers,
    )

    assert response.status_code == 422


def test_follow_up_action_table_privileges_allow_insert_select_deny_update_delete(
    db_session: Session,
) -> None:
    """DB-level backstop (spec I/O Matrix, "DB-level backstop"): the app role
    has `GRANT INSERT, SELECT` but not `UPDATE`/`DELETE` on `follow_up_action`
    (AD-6) — inspected directly from the Postgres catalog (`pg_class.relacl`
    via `aclexplode`) rather than `has_table_privilege`.

    `has_table_privilege` reflects *enforcement*: Postgres superusers bypass
    every ACL check unconditionally regardless of any GRANT/REVOKE issued
    against them, so that function always reports `True` for a superuser
    role no matter what the ACL actually says — and the local `sinaliza`
    role used by `TEST_DATABASE_URL`/`DATABASE_URL` is provisioned as a
    superuser in this environment (confirmed: `rolsuper = true`).
    `aclexplode` instead reflects what the migration/`conftest.py` actually
    *recorded* in the catalog, which is exactly what the AC asks to
    "inspect" — and is unaffected by superuser status, so this test always
    runs (never skips) regardless of the role's enforcement characteristics.
    """
    granted_privileges = (
        db_session.execute(
            text(
                """
                SELECT acl.privilege_type
                FROM pg_class c, aclexplode(c.relacl) acl
                WHERE c.relname = 'follow_up_action'
                  AND acl.grantee = (SELECT oid FROM pg_roles WHERE rolname = current_user)
                """
            )
        )
        .scalars()
        .all()
    )

    assert "INSERT" in granted_privileges
    assert "SELECT" in granted_privileges
    assert "UPDATE" not in granted_privileges
    assert "DELETE" not in granted_privileges
