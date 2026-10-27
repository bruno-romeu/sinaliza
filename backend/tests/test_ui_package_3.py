"""spec-ui-3 (detecção contra o próprio histórico): only concern-marked
observations are a signal, neutral ones are still cited as evidence once a
change exists, the observation flag goes through the API, the synthetic base
varies surnames, and `prepare_demo` fills the Home on a fresh base."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    AcademicPeriodModel,
    ClassroomModel,
    GradeModel,
    PedagogicalObservationModel,
    StudentModel,
    TrajectoryChangeModel,
)
from app.synthetic.names import compose_name
from app.synthetic.prepare_demo import prepare_demo
from tests.test_trajectory_detail import _add_earlier_period, _add_low_attendance, _auth_headers

AS_OF = "2026-09-24"


@pytest.fixture(autouse=True)
def _frozen_as_of(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", AS_OF)


def _observation(student_id, author_id, text: str, registers_concern: bool) -> PedagogicalObservationModel:
    return PedagogicalObservationModel(
        student_id=student_id,
        author_user_id=author_id,
        text=text,
        created_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        registers_concern=registers_concern,
    )


def test_neutral_observation_is_not_a_second_signal(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    _add_low_attendance(db_session, seeded_enrolled_student.id, seeded_classroom.id, 1, 2)
    db_session.add(
        _observation(
            seeded_enrolled_student.id,
            seeded_user.id,
            "Frequência dentro da faixa habitual neste período.",
            registers_concern=False,
        )
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    body = response.json()
    assert body["trajectory_change"] is None
    assert body["concerning_factor"]["kind"] == "ATTENDANCE"
    assert db_session.execute(select(TrajectoryChangeModel)).scalars().all() == []


def test_neutral_observation_is_cited_as_evidence_once_a_change_exists(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    _add_low_attendance(db_session, seeded_enrolled_student.id, seeded_classroom.id, 1, 2)
    _add_earlier_period(db_session, seeded_enrolled_student.id, seeded_classroom.id, "7.00")
    db_session.add(
        GradeModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            subject="Matemática",
            period_id=seeded_academic_period.id,
            date=date(2026, 9, 1),
            value=Decimal("4.00"),
        )
    )
    db_session.add(
        _observation(
            seeded_enrolled_student.id,
            seeded_user.id,
            "Participou menos das discussões.",
            registers_concern=False,
        )
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    body = response.json()
    assert body["trajectory_change"]["type"] == "COMBINED_DETERIORATION"
    # The neutral observation is evidence, but not part of the description.
    assert body["trajectory_change"]["description"] == (
        "Queda de frequência e queda de notas no 3º Bimestre Teste"
    )
    observation_items = [
        item for item in body["evidence"] if item["source_type"] == "PEDAGOGICAL_OBSERVATION"
    ]
    assert len(observation_items) == 1
    assert body["observations"][0]["registers_concern"] is False


def test_low_but_stable_grades_do_not_make_a_change(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    """The false positive that motivated spec-ui-3: average 3.5 after 3.0 was
    read as "queda de notas" because it sat under a fixed cut of 5."""
    _add_earlier_period(db_session, seeded_enrolled_student.id, seeded_classroom.id, "3.00")
    db_session.add(
        GradeModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            subject="Matemática",
            period_id=seeded_academic_period.id,
            date=date(2026, 9, 1),
            value=Decimal("3.50"),
        )
    )
    db_session.add(
        _observation(
            seeded_enrolled_student.id, seeded_user.id, "Registro com preocupação.", True
        )
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    body = response.json()
    assert body["trajectory_change"] is None
    assert body["concerning_factor"] == {
        "kind": "PEDAGOGICAL_OBSERVATION",
        "description": "Sinal isolado: preocupação registrada pela equipe no 3º Bimestre Teste",
    }


def test_post_observation_accepts_and_returns_registers_concern(
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
        "text": "Faltou às duas últimas avaliações.",
    }

    neutral = client.post("/pedagogical-observations", json=payload, headers=headers)
    concern = client.post(
        "/pedagogical-observations", json={**payload, "registers_concern": True}, headers=headers
    )

    assert neutral.status_code == 201
    assert neutral.json()["registers_concern"] is False
    assert concern.status_code == 201
    assert concern.json()["registers_concern"] is True
    flags = sorted(
        db_session.execute(select(PedagogicalObservationModel.registers_concern)).scalars().all()
    )
    assert flags == [False, True]


def test_synthetic_names_do_not_share_one_surname() -> None:
    names = [compose_name(index) for index in range(200)]

    assert len(set(names)) == 200
    assert len({name.split()[-1] for name in names}) > 5
    assert len({name.split()[1] for name in names}) > 5


def test_prepare_demo_computes_every_demo_trajectory(
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    _add_low_attendance(db_session, seeded_enrolled_student.id, seeded_classroom.id, 1, 2)
    db_session.add(
        _observation(seeded_enrolled_student.id, seeded_user.id, "Faltas frequentes.", True)
    )
    db_session.commit()

    students, changes = prepare_demo(db_session, window_days=30)

    assert (students, changes) == (1, 1)
    assert len(db_session.execute(select(TrajectoryChangeModel)).scalars().all()) == 1
