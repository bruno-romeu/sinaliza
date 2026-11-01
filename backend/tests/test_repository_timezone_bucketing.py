"""Day-bucketing of `timestamptz` columns must be UTC, never the Postgres
session's `timezone` GUC.

`deferred-work.md` carried this as "maybe-false" since the Story 3.2 code
review: `SqlAlchemyPedagogicalObservationRepository.list_by_student_in_range`
bucketed `created_at` (a `timestamptz`) with a plain `cast(created_at, Date)`,
whose day boundary Postgres resolves at the session's `timezone` setting —
unlike the native `Date` columns used everywhere else, and unlike `as_of()`,
`detected_at` derivation, and the rest of the system, which are all UTC.

It stayed "maybe" because the one environment anyone checked (this project's
own test/dev containers) reports `timezone = UTC`, where the cast happens to
be correct. That is a property of a container default, not of the code: a
client with a `PGTZ`, a `timezone=` in the connection URL, a pooler with its
own session defaults, or a different base image flips it, and then an
observation written near a day boundary silently buckets into the wrong
período day — skewing the PEDAGOGICAL_OBSERVATION convergence signal and the
`as_of()` truncation boundary at once.

These tests settle it by *forcing* a non-UTC session timezone and asserting
the bucketing does not move. They fail against the old `cast(..., Date)` and
pass with `base.utc_date_of`'s explicit `timezone('UTC', col)::date`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infrastructure.db.models import PedagogicalObservationModel, StudentModel, UserModel
from app.infrastructure.repositories.sqlalchemy_pedagogical_observation_repository import (
    SqlAlchemyPedagogicalObservationRepository,
)

# 2026-09-25T02:00Z is still 2026-09-24T23:00 in America/Sao_Paulo (UTC-3):
# the one timestamp whose bucket differs between the two readings.
CROSS_BOUNDARY_UTC = datetime(2026, 9, 25, 2, 0, tzinfo=UTC)
UTC_DAY = "2026-09-25"
SAO_PAULO_DAY = "2026-09-24"


@pytest.fixture(autouse=True)
def _as_of_after_both_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pinned past both candidate days so `filter_as_of` never decides the
    outcome — only the bucketing does."""
    monkeypatch.setenv("SINALIZA_DEMO_AS_OF", "2026-09-30")


@pytest.fixture()
def _non_utc_session(db_session: Session) -> None:
    """`SET LOCAL` so the change dies with this test's transaction and can
    never leak onto a pooled connection another test reuses."""
    db_session.execute(text("SET LOCAL TIME ZONE 'America/Sao_Paulo'"))
    assert db_session.execute(text("SHOW timezone")).scalar_one() == "America/Sao_Paulo"


def _seed_observation(
    db_session: Session, student: StudentModel, author: UserModel
) -> PedagogicalObservationModel:
    observation = PedagogicalObservationModel(
        student_id=student.id,
        author_user_id=author.id,
        text="Observação registrada perto da virada do dia.",
        created_at=CROSS_BOUNDARY_UTC,
        registers_concern=True,
    )
    db_session.add(observation)
    db_session.commit()
    db_session.refresh(observation)
    return observation


def test_observation_buckets_into_its_utc_day_under_a_non_utc_session(
    db_session: Session,
    seeded_enrolled_student: StudentModel,
    seeded_user: UserModel,
    _non_utc_session: None,
) -> None:
    observation = _seed_observation(db_session, seeded_enrolled_student, seeded_user)
    repository = SqlAlchemyPedagogicalObservationRepository(db_session)

    found = repository.list_by_student_in_range(
        seeded_enrolled_student.id,
        start_date=datetime.fromisoformat(UTC_DAY).date(),
        end_date=datetime.fromisoformat(UTC_DAY).date(),
    )

    assert [item.id for item in found] == [observation.id]


def test_observation_does_not_bucket_into_the_session_local_day(
    db_session: Session,
    seeded_enrolled_student: StudentModel,
    seeded_user: UserModel,
    _non_utc_session: None,
) -> None:
    """The other half of the same statement: under `America/Sao_Paulo` the
    old cast put this row on 2026-09-24. It must not be there."""
    _seed_observation(db_session, seeded_enrolled_student, seeded_user)
    repository = SqlAlchemyPedagogicalObservationRepository(db_session)

    found = repository.list_by_student_in_range(
        seeded_enrolled_student.id,
        start_date=datetime.fromisoformat(SAO_PAULO_DAY).date(),
        end_date=datetime.fromisoformat(SAO_PAULO_DAY).date(),
    )

    assert found == []


def test_bucketing_is_identical_under_utc_and_non_utc_sessions(
    db_session: Session,
    seeded_enrolled_student: StudentModel,
    seeded_user: UserModel,
) -> None:
    """The invariant stated directly: the same query answers the same thing
    whatever the session `timezone` happens to be."""
    observation = _seed_observation(db_session, seeded_enrolled_student, seeded_user)
    repository = SqlAlchemyPedagogicalObservationRepository(db_session)
    utc_day = datetime.fromisoformat(UTC_DAY).date()

    db_session.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    under_utc = [
        item.id
        for item in repository.list_by_student_in_range(
            seeded_enrolled_student.id, start_date=utc_day, end_date=utc_day
        )
    ]

    db_session.execute(text("SET LOCAL TIME ZONE 'America/Sao_Paulo'"))  # UTC-3
    under_sao_paulo = [
        item.id
        for item in repository.list_by_student_in_range(
            seeded_enrolled_student.id, start_date=utc_day, end_date=utc_day
        )
    ]

    assert under_utc == under_sao_paulo == [observation.id]
