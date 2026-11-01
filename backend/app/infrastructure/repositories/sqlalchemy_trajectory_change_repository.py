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
left completely untouched (no delete+reinsert) — the whole point of freezing.

Every read here — `get_by_id` included, since epic-5-retro-item-2 — goes
through `filter_as_of_timestamp` on `detected_at` (AD-5, AD-11); see
`get_by_id`'s own docstring for why that method was the remaining hole.
`upsert` is a write and is deliberately *not* truncated: detection persists
the change `as_of()` itself derived, and a write is never a "read of the
future"."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.trajectory_change import TrajectoryChange, TrajectoryChangeSource
from app.infrastructure.db.models import (
    FollowUpEvidenceModel,
    TrajectoryChangeModel,
    TrajectoryChangeSourceModel,
)
from app.infrastructure.repositories.base import filter_as_of_timestamp
from app.infrastructure.repositories.errors import translating_integrity_errors


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
        # An FK violation here (an already-deleted student/período) is
        # translated into `ForeignKeyViolationError` with the session rolled
        # back, instead of escaping raw and leaving the session unusable.
        with translating_integrity_errors(self._session):
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

        with translating_integrity_errors(self._session):
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
        `OpenFollowUpService` and `GetFollowUpService`.

        epic-5-retro-item-2: this used to be a plain
        `session.get(TrajectoryChangeModel, change_id)` with no date filter
        at all, while `list_recent` (Story 5.4) truncated at `as_of()` — the
        same "demo rewind leaks a later-dated row" bug class, one method
        away. A rehearsal that persisted a change under a later
        `SINALIZA_DEMO_AS_OF` and then rewound to an earlier date could
        still open a follow-up on it (`POST /follow-ups`) or read it back
        (`GET /follow-ups/{id}`) by id, even though Home and Trajectory had
        correctly stopped showing it. Now it answers `None` for a change
        dated after the current `as_of()`, exactly like every other
        trajectory-facing read.
        """
        stmt = filter_as_of_timestamp(
            select(TrajectoryChangeModel).where(TrajectoryChangeModel.id == change_id),
            TrajectoryChangeModel.detected_at,
        )
        model = self._session.execute(stmt).scalar_one_or_none()
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

    def count_recent(self) -> int:
        """Total behind `list_recent`, under the same `filter_as_of`."""
        stmt = filter_as_of_timestamp(
            select(func.count()).select_from(TrajectoryChangeModel),
            TrajectoryChangeModel.detected_at,
        )
        return self._session.execute(stmt).scalar_one()

    def list_recent(self, limit: int, offset: int = 0) -> list[TrajectoryChange]:
        """Home's only read of `TrajectoryChange` (spec-3-3 Boundaries &
        Constraints): rows by `detected_at` desc (then `id` desc, so pages
        never overlap or skip rows that share a `detected_at`), paginated by
        `limit`/`offset` since spec-ui-4 — `count_recent` gives the total.

        Also applies `filter_as_of` on `detected_at` (spec-5-4): `detected_at`
        is always written as `as_of()`'s own pinned date at insert time
        (`get_student_trajectory.py`), so this is a no-op under normal
        forward-moving demo time — but a demo rehearsal that rewinds
        `SINALIZA_DEMO_AS_OF` to an earlier date after a prior run already
        persisted a later-dated change would otherwise still surface that
        change in Home, a "future" leak relative to the rewound date.

        `detected_at` is bucketed to its **UTC** calendar date first, via
        `base.utc_date_of` — comparing the raw `timestamptz` to `as_of()`'s
        plain `date`, or casting it with a plain `::date`, would let Postgres
        resolve the day boundary at the session `timezone` GUC rather than at
        UTC, silently shifting the truncation boundary on a non-UTC
        session."""
        stmt = filter_as_of_timestamp(
            select(TrajectoryChangeModel), TrajectoryChangeModel.detected_at
        ).order_by(TrajectoryChangeModel.detected_at.desc(), TrajectoryChangeModel.id.desc())
        stmt = stmt.limit(limit).offset(offset)
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
