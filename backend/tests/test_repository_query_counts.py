"""Query-count regression tests for the read paths behind
`GET /follow-ups/{id}` and `GET /students/{id}/trajectory/detail`.

These exist because "is this an N+1?" is not a question to answer by
reading code: every number asserted below was measured by counting
statements on the engine (`before_cursor_execute`), not estimated. The
`count_queries` helper is the measurement instrument, and keeping it as a
test means the counts cannot silently regress later.

What it caught, and what it did not:

* `SqlAlchemyPedagogicalObservationRepository.get_by_ids` ran **three**
  queries for one batch — the rows, then `_restricted_ids`, then
  `_visible_to_user_ids`, the last two differing only by one join and one
  predicate. Merged into a single grouped query with
  `bool_or(responsible_user_id = :uid)`, so it is now **two**. Measured on
  `GET /follow-ups/{id}` with one cited observation: 14 → 13 statements.
* `GetFollowUpService` loops over `list_evidence_by_follow_up`'s rows and
  calls `TrajectoryChangeRepositoryPort.get_by_id` plus a full
  `resolve_evidence` per row — a genuine per-item fan-out that grows with
  the number of linked changes, and `GetHomeService` resolves
  `StudentRepositoryPort.get_by_id` once per listed change and per listed
  follow-up. Both loops live in `application/`, not in a repository, and
  fixing them means adding batch (`get_by_ids`) methods to the ports and
  rewriting those services — out of this change's scope. The test below
  pins the current per-change cost so the growth is at least visible and
  measured rather than assumed.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.domain.trajectory_change import SourceType, TrajectoryChangeType
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    FollowUpEvidenceModel,
    FollowUpModel,
    PedagogicalObservationModel,
    StudentModel,
    TrajectoryChangeModel,
    TrajectoryChangeSourceModel,
    UserModel,
)

AS_OF = "2026-09-24"


@pytest.fixture(autouse=True)
def _frozen_as_of(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", AS_OF)


@contextmanager
def count_queries(engine: Engine, counter: list[int]) -> Iterator[None]:
    """Counts every statement the engine actually sends to Postgres while the
    block runs — the measurement instrument this module's docstring refers
    to."""

    def _on_execute(conn, cursor, statement, parameters, context, executemany) -> None:
        counter[0] += 1

    event.listen(engine, "before_cursor_execute", _on_execute)
    try:
        yield
    finally:
        event.remove(engine, "before_cursor_execute", _on_execute)


def _auth_headers(client: TestClient, seeded_user: UserModel) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": seeded_user.email, "password": "Senha-Correta-123"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_follow_up_with_cited_observation(
    db_session: Session,
    student: StudentModel,
    period: AcademicPeriodModel,
    user: UserModel,
    changes: int = 1,
) -> uuid.UUID:
    """One `FollowUp` citing `changes` `TrajectoryChange`s, each with one
    `PedagogicalObservation` source — the shape `GET /follow-ups/{id}`
    resolves evidence for."""
    follow_up = FollowUpModel(
        id=uuid.uuid4(),
        student_id=student.id,
        status="EM_OBSERVACAO",
        reason=None,
        responsible_user_id=user.id,
        next_review_date=None,
        created_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
    )
    db_session.add(follow_up)
    db_session.flush()

    change_types = [
        TrajectoryChangeType.ATTENDANCE_DROP,
        TrajectoryChangeType.GRADE_DROP,
        TrajectoryChangeType.MISSING_ASSIGNMENTS_INCREASE,
        TrajectoryChangeType.COMBINED_DETERIORATION,
    ]
    for index in range(changes):
        observation = PedagogicalObservationModel(
            student_id=student.id,
            author_user_id=user.id,
            text=f"Observação {index}.",
            created_at=datetime(2026, 9, 1 + index, 12, 0, tzinfo=UTC),
            registers_concern=True,
        )
        change = TrajectoryChangeModel(
            id=uuid.uuid4(),
            student_id=student.id,
            type=change_types[index],
            period_id=period.id,
            detected_at=datetime(2026, 9, 10 + index, 0, 0, tzinfo=UTC),
            description="Mudança recente observada.",
        )
        db_session.add_all([observation, change])
        db_session.flush()
        db_session.add_all(
            [
                TrajectoryChangeSourceModel(
                    id=uuid.uuid4(),
                    trajectory_change_id=change.id,
                    source_type=SourceType.PEDAGOGICAL_OBSERVATION,
                    source_id=observation.id,
                ),
                FollowUpEvidenceModel(
                    id=uuid.uuid4(),
                    follow_up_id=follow_up.id,
                    trajectory_change_id=change.id,
                ),
            ]
        )
    db_session.commit()
    return follow_up.id


def test_get_follow_up_detail_costs_a_fixed_number_of_queries_for_one_change(
    client: TestClient,
    engine: Engine,
    db_session: Session,
    seeded_user: UserModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
) -> None:
    follow_up_id = _seed_follow_up_with_cited_observation(
        db_session, seeded_enrolled_student, seeded_academic_period, seeded_user
    )
    headers = _auth_headers(client, seeded_user)

    counter = [0]
    with count_queries(engine, counter):
        response = client.get(f"/follow-ups/{follow_up_id}", headers=headers)

    assert response.status_code == 200
    # Measured end to end (login excluded, it is outside the block):
    # 9 statements before merging the observation repository's two
    # restricted/visible lookups into one grouped query, 8 after.
    assert counter[0] == 8


def test_get_follow_up_detail_query_cost_grows_per_linked_trajectory_change(
    client: TestClient,
    engine: Engine,
    db_session: Session,
    seeded_user: UserModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
) -> None:
    """`GetFollowUpService` resolves each linked change separately, so the
    cost is linear in the number of linked changes, not constant. Pinned
    here, deliberately *not* fixed: the loop is in `application/`, and
    batching it means new port methods plus a service rewrite. See this
    module's docstring."""
    follow_up_id = _seed_follow_up_with_cited_observation(
        db_session, seeded_enrolled_student, seeded_academic_period, seeded_user, changes=3
    )
    headers = _auth_headers(client, seeded_user)

    counter = [0]
    with count_queries(engine, counter):
        response = client.get(f"/follow-ups/{follow_up_id}", headers=headers)

    assert response.status_code == 200
    assert len(response.json()["trajectory_changes"]) == 3
    # 8 for one change + 4 per additional change (get_by_id, its sources,
    # the observation rows, the visibility lookup). Before the merge it was
    # 9 + 5 per additional change — i.e. the per-change fan-out itself also
    # got one query cheaper.
    assert counter[0] == 8 + 2 * 4
