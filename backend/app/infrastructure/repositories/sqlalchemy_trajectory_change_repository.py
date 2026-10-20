"""Implements `TrajectoryChangeRepositoryPort` on top of SQLAlchemy — first
precedent in this codebase for `ON CONFLICT` (spec Code Map): no existing
repository idiom to mirror.

`upsert` is a single `INSERT ... ON CONFLICT (student_id, type, period_id) DO
UPDATE ... RETURNING id`, never a `SELECT`-then-`INSERT`/`UPDATE` (AD-1,
RF-11) — this is what makes two concurrent requests for the same
student/period resolve to the same row without an explicit lock (spec I/O
Matrix, "Concorrência"). The returned `id` is the *existing* row's id when a
conflict occurred (Postgres always returns the row actually written, never
the proposed-but-discarded one), so `TrajectoryChangeSource` rows below are
always attached to the real, stable id — never to whatever id the caller
happened to generate for a fresh `TrajectoryChange` object.

`sources` always fully replaces whatever `TrajectoryChangeSource` rows
already existed for this change (delete+reinsert, spec I/O Matrix:
"Recálculo do mesmo período... substituídos") in the same transaction as the
upsert — there is never a window where a `TrajectoryChange` exists without at
least one source row (RNF-11).

Story 4.1 adds the freeze-on-evidence guard deferred from Story 3.2: once a
`TrajectoryChange` has >=1 `FollowUpEvidence` row, the `ON CONFLICT ... DO
UPDATE` is scoped with a `WHERE NOT EXISTS (follow_up_evidence...)` clause, so
Postgres silently skips the update for a frozen row instead of touching it.
`RETURNING` only returns rows actually touched by the statement — a
`WHERE`-blocked `DO UPDATE` touches nothing — so `scalar_one_or_none()` is
used instead of `scalar_one()`; when it comes back `None` (frozen), the
existing row's current (frozen) values are fetched by a separate `SELECT` on
the `(student_id, type, period_id)` key, and `TrajectoryChangeSource` rows are
left completely untouched (no delete+reinsert) — the whole point of freezing."""

from __future__ import annotations

import uuid

from sqlalchemy import Date as SA_Date
from sqlalchemy import cast, delete, exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.trajectory_change import TrajectoryChange, TrajectoryChangeSource
from app.infrastructure.db.models import (
    FollowUpEvidenceModel,
    TrajectoryChangeModel,
    TrajectoryChangeSourceModel,
)
from app.infrastructure.repositories.base import filter_as_of


class SqlAlchemyTrajectoryChangeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self, change: TrajectoryChange, sources: list[TrajectoryChangeSource]
    ) -> TrajectoryChange:
        insert_stmt = insert(TrajectoryChangeModel).values(
            id=change.id,
            student_id=change.student_id,
            type=change.type,
            period_id=change.period_id,
            detected_at=change.detected_at,
            description=change.description,
        )
        # Skips the update entirely when the (about to be conflicted-on)
        # existing row already has >=1 FollowUpEvidence citing it (frozen,
        # spec Boundaries & Constraints).
        not_frozen = ~exists(
            select(FollowUpEvidenceModel.id).where(
                FollowUpEvidenceModel.trajectory_change_id == TrajectoryChangeModel.id
            )
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["student_id", "type", "period_id"],
            set_={
                "detected_at": insert_stmt.excluded.detected_at,
                "description": insert_stmt.excluded.description,
            },
            where=not_frozen,
        ).returning(TrajectoryChangeModel.id)
        change_id = self._session.execute(upsert_stmt).scalar_one_or_none()

        if change_id is None:
            # Frozen: the WHERE blocked the update, so nothing was returned.
            # Fetch the existing row's real (frozen) values by its natural
            # key instead of assuming they equal the proposed-but-rejected
            # `change` argument — and never touch TrajectoryChangeSource rows
            # in this branch.
            existing_stmt = select(TrajectoryChangeModel).where(
                TrajectoryChangeModel.student_id == change.student_id,
                TrajectoryChangeModel.type == change.type,
                TrajectoryChangeModel.period_id == change.period_id,
            )
            existing = self._session.execute(existing_stmt).scalar_one()
            # Only a SELECT happened in this branch (frozen row, no write) —
            # this commit merely closes the read-only transaction cleanly.
            self._session.commit()
            return TrajectoryChange(
                id=existing.id,
                student_id=existing.student_id,
                type=existing.type,
                period_id=existing.period_id,
                detected_at=existing.detected_at,
                description=existing.description,
            )

        self._session.execute(
            delete(TrajectoryChangeSourceModel).where(
                TrajectoryChangeSourceModel.trajectory_change_id == change_id
            )
        )
        for source in sources:
            self._session.add(
                TrajectoryChangeSourceModel(
                    id=source.id,
                    trajectory_change_id=change_id,
                    source_type=source.source_type,
                    source_id=source.source_id,
                )
            )

        self._session.commit()

        return TrajectoryChange(
            id=change_id,
            student_id=change.student_id,
            type=change.type,
            period_id=change.period_id,
            detected_at=change.detected_at,
            description=change.description,
        )

    def get_by_id(self, change_id: uuid.UUID) -> TrajectoryChange | None:
        """Story 4.1 — loads one `TrajectoryChange` by id for
        `OpenFollowUpService`."""
        model = self._session.get(TrajectoryChangeModel, change_id)
        if model is None:
            return None
        return TrajectoryChange(
            id=model.id,
            student_id=model.student_id,
            type=model.type,
            period_id=model.period_id,
            detected_at=model.detected_at,
            description=model.description,
        )

    def list_recent(self, limit: int) -> list[TrajectoryChange]:
        """Home's only read of `TrajectoryChange` (spec-3-3 Boundaries &
        Constraints): the `limit` most recent rows by `detected_at` desc,
        never a second page, never filtered/sorted any other way.

        Also applies `filter_as_of` on `detected_at` (spec-5-4): `detected_at`
        is always written as `as_of()`'s own pinned date at insert time
        (`get_student_trajectory.py`), so this is a no-op under normal
        forward-moving demo time — but a demo rehearsal that rewinds
        `SINALIZA_DEMO_AS_OF` to an earlier date after a prior run already
        persisted a later-dated change would otherwise still surface that
        change in Home, a "future" leak relative to the rewound date.

        `detected_at` is cast to `Date` first, mirroring
        `sqlalchemy_pedagogical_observation_repository.py`'s precedent for
        timestamp columns — comparing the raw `timestamptz` to `as_of()`'s
        plain `date` would let Postgres resolve the date literal at the
        session timezone's midnight rather than UTC midnight, silently
        shifting the truncation boundary on a non-UTC session."""
        detected_at_date = cast(TrajectoryChangeModel.detected_at, SA_Date)
        stmt = filter_as_of(select(TrajectoryChangeModel), detected_at_date).order_by(
            TrajectoryChangeModel.detected_at.desc(), TrajectoryChangeModel.id.desc()
        )
        stmt = stmt.limit(limit)
        models = self._session.execute(stmt).scalars().all()
        return [
            TrajectoryChange(
                id=model.id,
                student_id=model.student_id,
                type=model.type,
                period_id=model.period_id,
                detected_at=model.detected_at,
                description=model.description,
            )
            for model in models
        ]

    def list_sources_by_change(self, change_id) -> list[TrajectoryChangeSource]:
        """Story 3.4 — every `TrajectoryChangeSource` row attached to
        `change_id`, feeding `GetStudentTrajectoryDetailService`'s evidence
        resolution (RNF-11: never a free-text-only citation)."""
        stmt = select(TrajectoryChangeSourceModel).where(
            TrajectoryChangeSourceModel.trajectory_change_id == change_id
        )
        models = self._session.execute(stmt).scalars().all()
        return [
            TrajectoryChangeSource(
                id=model.id,
                trajectory_change_id=model.trajectory_change_id,
                source_type=model.source_type,
                source_id=model.source_id,
            )
            for model in models
        ]
