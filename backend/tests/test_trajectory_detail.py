"""Covers the spec's I/O & Edge-Case Matrix for `GET
/students/{id}/trajectory/detail` (Story 3.4)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.assignment_submission import AssignmentSubmissionStatus
from app.domain.attendance import AttendanceStatus
from app.domain.student import DatasetSplit
from app.domain.user import UserRole
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    AssignmentModel,
    AssignmentSubmissionModel,
    AttendanceRecordModel,
    ClassroomModel,
    GradeModel,
    PedagogicalObservationModel,
    StudentModel,
    UserModel,
)
from app.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher

STUDENT_NOT_FOUND_BODY = {
    "error": {"code": "student_not_found", "message": "Estudante não encontrado."}
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


def _add_low_attendance(
    db_session: Session, student_id, classroom_id, present_count: int, absent_count: int
) -> None:
    day = date(2026, 8, 1)
    for _ in range(present_count):
        db_session.add(
            AttendanceRecordModel(
                student_id=student_id, classroom_id=classroom_id, date=day, status=AttendanceStatus.PRESENT
            )
        )
        day += timedelta(days=1)
    for _ in range(absent_count):
        db_session.add(
            AttendanceRecordModel(
                student_id=student_id,
                classroom_id=classroom_id,
                date=day,
                status=AttendanceStatus.ABSENT_UNJUSTIFIED,
            )
        )
        day += timedelta(days=1)


# --- Change detected ---------------------------------------------------------------


def test_detail_with_detected_change_includes_resolved_evidence_and_omits_concerning_factor(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    _add_low_attendance(db_session, seeded_enrolled_student.id, seeded_classroom.id, 1, 2)
    db_session.add(
        PedagogicalObservationModel(
            student_id=seeded_enrolled_student.id,
            author_user_id=seeded_user.id,
            text="Observação de teste.",
            created_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()

    # ATTENDANCE + PEDAGOGICAL_OBSERVATION confirm -> ATTENDANCE_DROP ->
    # chart_indicator deterministically attendance_rate (spec Boundaries).
    assert body["chart_indicator"] == "attendance_rate"
    assert body["trajectory_change"] is not None
    assert body["trajectory_change"]["type"] == "ATTENDANCE_DROP"
    assert body["concerning_factor"] is None

    # Every evidence item traces to a real source record, never free text
    # alone (RNF-11).
    assert len(body["evidence"]) == 4
    source_types = {item["source_type"] for item in body["evidence"]}
    assert source_types == {"ATTENDANCE_RECORD", "PEDAGOGICAL_OBSERVATION"}
    for item in body["evidence"]:
        assert item["description"]
        assert item["date"]

    observation_items = [
        item for item in body["evidence"] if item["source_type"] == "PEDAGOGICAL_OBSERVATION"
    ]
    assert observation_items[0]["description"] == "Registro pedagógico em 01/09/2026: Observação de teste."

    # Series covers the (single) seeded período.
    assert len(body["series"]) == 1
    assert body["series"][0]["period_id"] == str(seeded_academic_period.id)
    assert body["series"][0]["period_label"] == seeded_academic_period.label


# --- Calm state ---------------------------------------------------------------------


def test_detail_calm_state_has_no_change_no_concerning_factor_no_evidence(
    client: TestClient,
    seeded_user,
    db_session: Session,
) -> None:
    bare_student = StudentModel(name="Estudante Sem Dados", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add(bare_student)
    db_session.commit()

    response = client.get(
        f"/students/{bare_student.id}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trajectory_change"] is None
    assert body["concerning_factor"] is None
    assert body["evidence"] == []
    assert body["chart_indicator"] == "attendance_rate"
    # No history at all -> fewer than 2 non-null points -> no fabricated range.
    assert body["habitual_range"] is None
    assert body["observations"] == []
    # No `AcademicPeriod`s seeded at all (fresh-environment case) -> empty
    # series, not an error (code review finding, Story 3.4).
    assert body["series"] == []


# --- Concerning factor only ----------------------------------------------------------


def test_detail_with_single_confirmed_signal_has_concerning_factor_and_no_evidence(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    db_session.add_all(
        [
            # current window [2026-08-25, 2026-09-24]
            AttendanceRecordModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 9, 20),
                status=AttendanceStatus.PRESENT,
            ),
            AttendanceRecordModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 9, 21),
                status=AttendanceStatus.ABSENT_UNJUSTIFIED,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trajectory_change"] is None
    assert body["concerning_factor"] == {
        "kind": "ATTENDANCE",
        "description": "Sinal isolado: queda de frequência no 3º Bimestre Teste",
    }
    # No stable id for a concerning factor -> no evidence list.
    assert body["evidence"] == []


# --- Habitual range: >=2 history points ------------------------------------------------


def test_detail_habitual_range_is_min_max_of_students_own_series(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    previous_period = AcademicPeriodModel(
        label="2º Bimestre Teste",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 7, 26),
        order_index=2,
    )
    db_session.add(previous_period)
    db_session.flush()

    # Previous período: 1/1 present -> rate 1.0 within its own ending window.
    db_session.add(
        AttendanceRecordModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            date=date(2026, 7, 20),
            status=AttendanceStatus.PRESENT,
        )
    )
    # Current período: 1 present + 1 absent -> rate 0.5.
    db_session.add_all(
        [
            AttendanceRecordModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 9, 20),
                status=AttendanceStatus.PRESENT,
            ),
            AttendanceRecordModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 9, 21),
                status=AttendanceStatus.ABSENT_UNJUSTIFIED,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["series"]) == 2
    # Ordered by start_date ascending.
    assert body["series"][0]["period_id"] == str(previous_period.id)
    assert body["series"][1]["period_id"] == str(seeded_academic_period.id)
    assert body["habitual_range"] is not None
    assert Decimal(body["habitual_range"]["low"]) == Decimal("0.5")
    assert Decimal(body["habitual_range"]["high"]) == Decimal("1.0")


# --- Unknown/TRAIN student -----------------------------------------------------------


def test_detail_for_unknown_student_returns_404(client: TestClient, seeded_user) -> None:
    response = client.get(
        f"/students/{uuid.uuid4()}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 404
    assert response.json() == STUDENT_NOT_FOUND_BODY


def test_detail_for_train_split_student_returns_identical_404(
    client: TestClient, seeded_user, db_session: Session
) -> None:
    train_student = StudentModel(name="Aluno de Treino", dataset_split=DatasetSplit.TRAIN)
    db_session.add(train_student)
    db_session.commit()

    response = client.get(
        f"/students/{train_student.id}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 404
    assert response.json() == STUDENT_NOT_FOUND_BODY


# --- Chart-indicator selection per trajectory_change type -----------------------------


def test_detail_chart_indicator_follows_grade_drop_change_type(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    db_session.add(
        GradeModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            subject="Matemática",
            period_id=seeded_academic_period.id,
            date=date(2026, 9, 1),
            value=Decimal("3.00"),
        )
    )
    db_session.add(
        PedagogicalObservationModel(
            student_id=seeded_enrolled_student.id,
            author_user_id=seeded_user.id,
            text="Observação de teste.",
            created_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trajectory_change"]["type"] == "GRADE_DROP"
    assert body["chart_indicator"] == "grade_average"
    evidence_source_types = {item["source_type"] for item in body["evidence"]}
    assert evidence_source_types == {"GRADE", "PEDAGOGICAL_OBSERVATION"}


def test_detail_chart_indicator_follows_missing_assignments_change_type(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    for i in range(2):
        assignment = AssignmentModel(
            classroom_id=seeded_classroom.id,
            subject="Matemática",
            period_id=seeded_academic_period.id,
            due_date=date(2026, 9, 10 + i),
        )
        db_session.add(assignment)
        db_session.flush()
        db_session.add(
            AssignmentSubmissionModel(
                assignment_id=assignment.id,
                student_id=seeded_enrolled_student.id,
                status=AssignmentSubmissionStatus.NOT_DELIVERED,
                date=date(2026, 9, 10 + i),
            )
        )
    db_session.add(
        PedagogicalObservationModel(
            student_id=seeded_enrolled_student.id,
            author_user_id=seeded_user.id,
            text="Observação de teste.",
            created_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trajectory_change"]["type"] == "MISSING_ASSIGNMENTS_INCREASE"
    assert body["chart_indicator"] == "missing_assignments_count"
    # ASSIGNMENT_SUBMISSION is the only non-PEDAGOGICAL_OBSERVATION source for
    # this change type -- resolved into a factual description, never a
    # free-text-only citation (RNF-11; code review finding, Story 3.4).
    evidence_source_types = {item["source_type"] for item in body["evidence"]}
    assert evidence_source_types == {"ASSIGNMENT_SUBMISSION", "PEDAGOGICAL_OBSERVATION"}
    submission_items = [
        item for item in body["evidence"] if item["source_type"] == "ASSIGNMENT_SUBMISSION"
    ]
    assert len(submission_items) == 2
    assert submission_items[0]["description"] == "Atividade não entregue em 10/09/2026"
    assert submission_items[0]["date"] == "2026-09-10"


def test_detail_chart_indicator_follows_combined_deterioration_change_type(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    """ATTENDANCE + GRADE both confirm -> COMBINED_DETERIORATION -> spec
    Boundaries mandate `attendance_rate` for this type (same as the lone-signal
    ATTENDANCE_DROP case)."""
    _add_low_attendance(db_session, seeded_enrolled_student.id, seeded_classroom.id, 1, 2)
    db_session.add(
        GradeModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            subject="Matemática",
            period_id=seeded_academic_period.id,
            date=date(2026, 9, 1),
            value=Decimal("3.00"),
        )
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trajectory_change"]["type"] == "COMBINED_DETERIORATION"
    assert body["chart_indicator"] == "attendance_rate"


# --- window_days override ---------------------------------------------------------------


def test_detail_window_days_query_param_overrides_default(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    """Mirrors `test_trajectory.py`'s coverage of the identical query param on
    the sibling `/trajectory` route — a record outside the default 30-day
    window only surfaces once `?window_days=` widens it."""
    db_session.add(
        AttendanceRecordModel(
            student_id=seeded_enrolled_student.id,
            classroom_id=seeded_classroom.id,
            date=date(2026, 8, 20),
            status=AttendanceStatus.PRESENT,
        )
    )
    db_session.commit()
    headers = _auth_headers(client, seeded_user)

    default_window = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail", headers=headers
    )
    widened_window = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail?window_days=40",
        headers=headers,
    )

    assert default_window.json()["series"][0]["value"] is None
    assert widened_window.json()["series"][0]["value"] == "1.0000"
    # The override only widens the series' rolling window — it must not
    # perturb the independent, period-bounded convergence/concerning-factor
    # read (code review finding, Story 3.4).
    assert default_window.json()["trajectory_change"] == widened_window.json()["trajectory_change"]
    assert (
        default_window.json()["concerning_factor"] == widened_window.json()["concerning_factor"]
    )


# --- Current-period series point anchors on the real clock, not a future end_date ------


def test_detail_current_period_series_point_anchors_on_real_clock_not_future_end_date(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mid-period view: `seeded_academic_period` runs 2026-07-27..2026-09-25,
    but "today" is only 2026-08-10, two weeks in. The series point for this
    still-open current period must use the default 30-day window ending at
    `as_of()` (2026-08-10) -- never a window ending at the period's future
    `end_date` (2026-09-25), which would reach past "today" into dates with
    no attendance recorded yet and silently yield `None` (code review
    finding, Story 3.4)."""
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", "2026-08-10")
    db_session.add_all(
        [
            AttendanceRecordModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 8, 5),
                status=AttendanceStatus.PRESENT,
            ),
            AttendanceRecordModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 8, 6),
                status=AttendanceStatus.PRESENT,
            ),
            AttendanceRecordModel(
                student_id=seeded_enrolled_student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 8, 7),
                status=AttendanceStatus.ABSENT_UNJUSTIFIED,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["series"]) == 1
    # 2/3 present within [as_of() - 30, as_of()] = [2026-07-11, 2026-08-10] --
    # anchoring on the future end_date instead would place this window at
    # [2026-08-26, 2026-09-25], excluding all three records and yielding
    # `None`.
    assert Decimal(body["series"][0]["value"]) == Decimal("0.6667")


# --- Observations timeline ------------------------------------------------------------


def test_detail_observations_are_capped_at_ten_desc_by_date(
    client: TestClient,
    seeded_user,
    seeded_enrolled_student: StudentModel,
    db_session: Session,
) -> None:
    for i in range(12):
        db_session.add(
            PedagogicalObservationModel(
                student_id=seeded_enrolled_student.id,
                author_user_id=seeded_user.id,
                text=f"Observação {i}.",
                created_at=datetime(2026, 1, 1 + i, 12, 0, tzinfo=timezone.utc),
            )
        )
    db_session.commit()

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail",
        headers=_auth_headers(client, seeded_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["observations"]) == 10
    dates = [observation["date"] for observation in body["observations"]]
    assert dates == sorted(dates, reverse=True)
    assert body["observations"][0]["text"] == "Observação 11."


# --- Story 4.4: RF-22 visibility scoping of PedagogicalObservation evidence --------------

_RESTRICTED_TEXT = (
    "Texto do registro pedagógico restrito ao responsável pelo "
    "acompanhamento que o cita como evidência."
)


def _create_user(db_session: Session, email: str) -> UserModel:
    hasher = BcryptPasswordHasher()
    user = UserModel(
        name="Outra Coordenação",
        email=email,
        password_hash=hasher.hash("Senha-Correta-123"),
        role=UserRole.COORDENACAO_PEDAGOGICA,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_detail_evidence_redacts_observation_text_once_cited_by_a_follow_up_for_other_users(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    _add_low_attendance(db_session, seeded_enrolled_student.id, seeded_classroom.id, 1, 2)
    db_session.add(
        PedagogicalObservationModel(
            student_id=seeded_enrolled_student.id,
            author_user_id=seeded_user.id,
            text="Observação de teste.",
            created_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    headers = _auth_headers(client, seeded_user)

    # Before any FollowUp cites it: visible to anyone (unrestricted default).
    before = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail", headers=headers
    ).json()
    change_id = before["trajectory_change"]["id"]
    observation_before = next(
        item for item in before["evidence"] if item["source_type"] == "PEDAGOGICAL_OBSERVATION"
    )
    assert "Observação de teste." in observation_before["description"]

    # Open a FollowUp citing this change -- the observation becomes restricted.
    open_response = client.post(
        "/follow-ups",
        json={
            "student_id": str(seeded_enrolled_student.id),
            "trajectory_change_id": change_id,
        },
        headers=headers,
    )
    assert open_response.status_code == 201

    # Responsible user still sees the real text.
    own_detail = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail", headers=headers
    ).json()
    own_observation = next(
        item
        for item in own_detail["evidence"]
        if item["source_type"] == "PEDAGOGICAL_OBSERVATION"
    )
    assert "Observação de teste." in own_observation["description"]

    # A different authenticated user is redacted.
    other_user = _create_user(db_session, "outra.coordenacao@escola.test")
    other_headers = _auth_headers(client, other_user)
    other_detail = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail", headers=other_headers
    ).json()
    other_observation = next(
        item
        for item in other_detail["evidence"]
        if item["source_type"] == "PEDAGOGICAL_OBSERVATION"
    )
    assert "Observação de teste." not in other_observation["description"]
    assert _RESTRICTED_TEXT in other_observation["description"]


def test_detail_timeline_redacts_observation_text_once_cited_by_a_follow_up_for_other_users(
    client: TestClient,
    seeded_user,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
    db_session: Session,
) -> None:
    _add_low_attendance(db_session, seeded_enrolled_student.id, seeded_classroom.id, 1, 2)
    db_session.add(
        PedagogicalObservationModel(
            student_id=seeded_enrolled_student.id,
            author_user_id=seeded_user.id,
            text="Observação de teste.",
            created_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    headers = _auth_headers(client, seeded_user)

    before = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail", headers=headers
    ).json()
    change_id = before["trajectory_change"]["id"]
    assert before["observations"][0]["text"] == "Observação de teste."

    open_response = client.post(
        "/follow-ups",
        json={
            "student_id": str(seeded_enrolled_student.id),
            "trajectory_change_id": change_id,
        },
        headers=headers,
    )
    assert open_response.status_code == 201

    # Responsible user still sees the real text in the timeline.
    own_detail = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail", headers=headers
    ).json()
    assert own_detail["observations"][0]["text"] == "Observação de teste."

    # A different authenticated user is redacted in the timeline too (RF-22).
    other_user = _create_user(db_session, "outra.coordenacao.timeline@escola.test")
    other_headers = _auth_headers(client, other_user)
    other_detail = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail", headers=other_headers
    ).json()
    assert other_detail["observations"][0]["text"] == _RESTRICTED_TEXT


# --- Unauthenticated -------------------------------------------------------------------


def test_detail_without_bearer_token_returns_401(
    client: TestClient, seeded_enrolled_student: StudentModel
) -> None:
    response = client.get(f"/students/{seeded_enrolled_student.id}/trajectory/detail")

    assert response.status_code == 401
    assert "error" in response.json()
