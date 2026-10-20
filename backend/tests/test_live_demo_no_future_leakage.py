"""spec-5-4: one consolidated, demo-specific proof that the live demo's read
surfaces (`GET /students/{id}/trajectory`, `GET /home`, `GET /home/search`)
never expose a fact dated after `SINALIZA_DEMO_AS_OF`/`as_of()`, and never
expose a `TRAIN`-split student — a guarantee that was previously only proven
per-repository (`test_trajectory.py`, `test_home.py`) or by code inspection,
never as one named end-to-end invariant covering the actual live demo path.

Also regression-covers the one real gap this story's investigation found:
`GetHomeService`'s only read of `TrajectoryChange` (`list_recent`) had no
`as_of()` filter at all — a demo rehearsal that rewinds `SINALIZA_DEMO_AS_OF`
to an earlier date after a prior run already persisted a later-dated change
would otherwise still surface that change in Home, a leak of "the future"
relative to the rewound date. Fixed in
`sqlalchemy_trajectory_change_repository.py`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.attendance import AttendanceStatus
from app.domain.student import DatasetSplit
from app.domain.trajectory_change import TrajectoryChangeType
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    AttendanceRecordModel,
    ClassroomModel,
    EnrollmentModel,
    StudentModel,
    TrajectoryChangeModel,
)

# Falls inside `seeded_academic_period`'s window (2026-07-27 .. 2026-09-25),
# mirroring `test_trajectory.py`/`test_home.py`'s precedent.
AS_OF = "2026-09-24"


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
) -> TrajectoryChangeModel:
    change = TrajectoryChangeModel(
        student_id=student.id,
        type=TrajectoryChangeType.ATTENDANCE_DROP,
        period_id=period.id,
        detected_at=detected_at,
        description="Mudança recente: teste — vazamento de futuro",
    )
    db_session.add(change)
    db_session.commit()
    return change


# --- EVAL_DEMO student: no fact dated after as_of() ever surfaces ---------------


def test_trajectory_and_home_never_reflect_facts_after_as_of(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", AS_OF)

    db_session.add_all(
        [
            AttendanceRecordModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 9, 20),
                status=AttendanceStatus.PRESENT,
            ),
            # Dated after as_of() — exists in the full synthetic year but
            # must never be visible while the demo is pinned to AS_OF.
            AttendanceRecordModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 9, 26),
                status=AttendanceStatus.ABSENT_UNJUSTIFIED,
            ),
        ]
    )
    db_session.commit()

    headers = _auth_headers(client, seeded_user)
    trajectory_response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory?window_days=10",
        headers=headers,
    )
    assert trajectory_response.status_code == 200
    # Only the pre-as_of PRESENT record is in window — a leaked post-as_of
    # ABSENT record would pull this below 1.0.
    assert Decimal(trajectory_response.json()["attendance_rate"]) == Decimal("1.0000")

    # A change detected and persisted exactly at as_of() is the only one
    # Home should ever show for this student.
    _add_change(
        db_session,
        seeded_enrolled_student,
        seeded_academic_period,
        datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc),
    )

    home_response = client.get("/home", headers=headers)
    assert home_response.status_code == 200
    assert [c["student_id"] for c in home_response.json()["recent_changes"]] == [
        str(seeded_enrolled_student.id)
    ]


# --- Rewinding as_of() must hide a previously-visible later change -------------


def test_rewinding_as_of_hides_a_previously_detected_change(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    later_as_of = "2026-09-24"
    earlier_as_of = "2026-09-10"  # rehearsal rewind to an earlier "today"

    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", later_as_of)
    _add_change(
        db_session,
        seeded_enrolled_student,
        seeded_academic_period,
        datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc),
    )

    headers = _auth_headers(client, seeded_user)
    first_response = client.get("/home", headers=headers)
    assert first_response.status_code == 200
    assert len(first_response.json()["recent_changes"]) == 1

    # Rewind: a second rehearsal run pins an earlier "today". The change
    # persisted above is now dated after the (rewound) current as_of() and
    # must disappear, not linger as a "future" leak.
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", earlier_as_of)

    second_response = client.get("/home", headers=headers)
    assert second_response.status_code == 200
    assert second_response.json()["recent_changes"] == []


# --- TRAIN-split student: invisible across every live demo surface -----------


def test_train_split_student_invisible_across_trajectory_home_and_search(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", AS_OF)

    train_student = StudentModel(name="Estudante Treino", dataset_split=DatasetSplit.TRAIN)
    db_session.add(train_student)
    db_session.flush()
    db_session.add(
        EnrollmentModel(student_id=train_student.id, classroom_id=seeded_classroom.id)
    )
    db_session.add(
        AttendanceRecordModel(
            student_id=train_student.id,
            classroom_id=seeded_classroom.id,
            date=date(2026, 9, 20),
            status=AttendanceStatus.PRESENT,
        )
    )
    db_session.commit()
    _add_change(
        db_session,
        train_student,
        seeded_academic_period,
        datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc),
    )

    headers = _auth_headers(client, seeded_user)

    trajectory_response = client.get(
        f"/students/{train_student.id}/trajectory", headers=headers
    )
    assert trajectory_response.status_code == 404

    home_response = client.get("/home", headers=headers)
    assert home_response.status_code == 200
    assert home_response.json()["recent_changes"] == []

    search_response = client.get(
        "/home/search?q=Estudante Treino", headers=headers
    )
    assert search_response.status_code == 200
    assert search_response.json() == {"count": 0, "results": []}
