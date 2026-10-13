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
least one source row (RNF-11). No freeze-on-evidence guard here: the upsert
is always unconditional `DO UPDATE` (spec Never, `deferred-work.md` — Epic 4
adds the guard once `follow_up_evidence` exists)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.trajectory_change import TrajectoryChange, TrajectoryChangeSource
from app.infrastructure.db.models import TrajectoryChangeModel, TrajectoryChangeSourceModel


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
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["student_id", "type", "period_id"],
            set_={
                "detected_at": insert_stmt.excluded.detected_at,
                "description": insert_stmt.excluded.description,
            },
        ).returning(TrajectoryChangeModel.id)
        change_id = self._session.execute(upsert_stmt).scalar_one()

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

    def list_recent(self, limit: int) -> list[TrajectoryChange]:
        """Home's only read of `TrajectoryChange` (spec-3-3 Boundaries &
        Constraints): the `limit` most recent rows by `detected_at` desc,
        never a second page, never filtered/sorted any other way."""
        stmt = (
            select(TrajectoryChangeModel)
            .order_by(TrajectoryChangeModel.detected_at.desc(), TrajectoryChangeModel.id.desc())
            .limit(limit)
        )
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
