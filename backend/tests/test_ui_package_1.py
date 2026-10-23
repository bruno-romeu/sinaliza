"""spec-ui-1 (pacote de backend para o design system): no duplicate open
follow-up per student/responsible user, student name + classroom and the open
follow-up id on the trajectory detail, and on-screen texts without dashes."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.trajectory.evidence import _format_grade_br, _grade_description
from app.domain.follow_up import FollowUpStatus
from app.domain.grade import Grade
from app.domain.trajectory_change import TrajectoryChangeType
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    ClassroomModel,
    FollowUpEvidenceModel,
    FollowUpModel,
    StudentModel,
    TrajectoryChangeModel,
)
from tests.test_follow_ups import (
    AS_OF,
    _auth_headers,
    _create_user,
    _detect_attendance_drop_change,
)


@pytest.fixture(autouse=True)
def _frozen_as_of(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", AS_OF)


def _open(client: TestClient, headers: dict[str, str], student_id, change_id) -> tuple[int, dict]:
    response = client.post(
        "/follow-ups",
        json={"student_id": str(student_id), "trajectory_change_id": str(change_id)},
        headers=headers,
    )
    return response.status_code, response.json()


def _follow_ups(db_session: Session, student_id) -> list[FollowUpModel]:
    return list(
        db_session.execute(select(FollowUpModel).where(FollowUpModel.student_id == student_id))
        .scalars()
        .all()
    )


def _evidence_rows(db_session: Session, follow_up_id) -> list[FollowUpEvidenceModel]:
    return list(
        db_session.execute(
            select(FollowUpEvidenceModel).where(
                FollowUpEvidenceModel.follow_up_id == uuid.UUID(str(follow_up_id))
            )
        )
        .scalars()
        .all()
    )


# --- Acompanhamento duplicado ----------------------------------------------------------


def test_opening_twice_for_the_same_change_reuses_the_open_follow_up(
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

    first_status, first = _open(client, headers, seeded_enrolled_student.id, change["id"])
    second_status, second = _open(client, headers, seeded_enrolled_student.id, change["id"])

    assert first_status == 201
    assert second_status == 200
    assert second["id"] == first["id"]
    assert len(_follow_ups(db_session, seeded_enrolled_student.id)) == 1
    assert len(_evidence_rows(db_session, first["id"])) == 1


def test_opening_for_a_new_change_attaches_it_to_the_open_follow_up(
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
    _, opened = _open(client, headers, seeded_enrolled_student.id, change["id"])

    other_change = TrajectoryChangeModel(
        id=uuid.uuid4(),
        student_id=seeded_enrolled_student.id,
        type=TrajectoryChangeType.GRADE_DROP,
        period_id=seeded_academic_period.id,
        detected_at=datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
        description="Queda de notas no 3º Bimestre Teste",
    )
    db_session.add(other_change)
    db_session.commit()

    status, body = _open(client, headers, seeded_enrolled_student.id, other_change.id)

    assert status == 200
    assert body["id"] == opened["id"]
    linked = {row.trajectory_change_id for row in _evidence_rows(db_session, opened["id"])}
    assert linked == {uuid.UUID(change["id"]), other_change.id}

    detail = client.get(f"/follow-ups/{opened['id']}", headers=headers).json()
    assert len(detail["trajectory_changes"]) == 2


def test_after_closing_a_new_click_creates_a_new_follow_up(
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
    _, first = _open(client, headers, seeded_enrolled_student.id, change["id"])
    closed = client.patch(
        f"/follow-ups/{first['id']}/status", json={"status": "ENCERRADO"}, headers=headers
    )
    assert closed.status_code == 200

    status, second = _open(client, headers, seeded_enrolled_student.id, change["id"])

    assert status == 201
    assert second["id"] != first["id"]
    statuses = {row.status for row in _follow_ups(db_session, seeded_enrolled_student.id)}
    assert statuses == {FollowUpStatus.ENCERRADO, FollowUpStatus.EM_OBSERVACAO}


def test_reuse_is_scoped_to_the_responsible_user(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    """Writes on a FollowUp belong to its responsible user (RF-22), so another
    user's click opens their own follow-up instead of reusing one they could
    not act on."""
    headers = _auth_headers(client, seeded_user)
    change = _detect_attendance_drop_change(
        client, headers, db_session, seeded_enrolled_student, seeded_classroom, seeded_user.id
    )
    _, first = _open(client, headers, seeded_enrolled_student.id, change["id"])

    other_user = _create_user(db_session, "outra.coordenacao@escola.test")
    other_headers = _auth_headers(client, other_user)
    status, second = _open(client, other_headers, seeded_enrolled_student.id, change["id"])

    assert status == 201
    assert second["id"] != first["id"]


# --- Nome, turma e acompanhamento aberto na trajetória ----------------------------------


def test_trajectory_detail_includes_student_and_open_follow_up_id(
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

    before = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail", headers=headers
    ).json()
    assert before["student"] == {
        "id": str(seeded_enrolled_student.id),
        "name": seeded_enrolled_student.name,
        "classroom_name": seeded_classroom.name,
    }
    assert before["open_follow_up_id"] is None

    _, opened = _open(client, headers, seeded_enrolled_student.id, change["id"])
    after = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail", headers=headers
    ).json()
    assert after["open_follow_up_id"] == opened["id"]

    client.patch(
        f"/follow-ups/{opened['id']}/status", json={"status": "ENCERRADO"}, headers=headers
    )
    closed = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail", headers=headers
    ).json()
    assert closed["open_follow_up_id"] is None


def test_open_follow_up_id_is_scoped_to_the_requesting_user(
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
    _open(client, headers, seeded_enrolled_student.id, change["id"])

    other_user = _create_user(db_session, "terceira.coordenacao@escola.test")
    other = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail",
        headers=_auth_headers(client, other_user),
    ).json()
    assert other["open_follow_up_id"] is None
    assert other["student"]["name"] == seeded_enrolled_student.name


# --- Textos sem travessão e notas formatadas ------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("4.50"), "4,5"),
        (Decimal("7.00"), "7,0"),
        (Decimal("7.25"), "7,25"),
        (Decimal("10"), "10,0"),
        (Decimal("0"), "0,0"),
    ],
)
def test_format_grade_br(value: Decimal, expected: str) -> None:
    assert _format_grade_br(value) == expected


def test_grade_evidence_description_has_no_dash() -> None:
    grade = Grade(
        id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        classroom_id=uuid.uuid4(),
        subject="Matemática",
        period_id=uuid.uuid4(),
        date=date(2026, 9, 8),
        value=Decimal("4.50"),
    )

    assert _grade_description(grade) == "Nota 4,5 em Matemática em 08/09/2026"
