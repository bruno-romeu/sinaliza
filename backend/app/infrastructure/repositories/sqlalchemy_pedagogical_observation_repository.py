"""Implements `PedagogicalObservationRepositoryPort` on top of SQLAlchemy.

`save` never needs to translate an `IntegrityError` into a domain error —
`pedagogical_observations` carries no UNIQUE constraint (spec Boundaries &
Constraints: multiple observations for the same student are expected and
valid, each a new row, same precedent as `Grade`/`AssignmentSubmission`).

`list_by_student_in_range` (Story 3.2) feeds the pedagogical
`SignalEvaluator` — it filters on `created_at`'s date, mirroring
`SqlAlchemyAttendanceRepository.list_by_student_in_range`'s shape, and applies
`filter_as_of` (AD-11) as the same leak-prevention invariant every other
trajectory-facing read already carries."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import cast, select
from sqlalchemy import Date as SA_Date
from sqlalchemy.orm import Session

from app.domain.pedagogical_observation import PedagogicalObservation
from app.infrastructure.db.models import PedagogicalObservationModel
from app.infrastructure.repositories.base import filter_as_of


class SqlAlchemyPedagogicalObservationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        student_id: uuid.UUID,
        author_user_id: uuid.UUID,
        text: str,
        created_at: datetime,
    ) -> PedagogicalObservation:
        model = PedagogicalObservationModel(
            student_id=student_id,
            author_user_id=author_user_id,
            text=text,
            created_at=created_at,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return PedagogicalObservation(
            id=model.id,
            student_id=model.student_id,
            author_user_id=model.author_user_id,
            text=model.text,
            created_at=model.created_at,
        )

    def list_by_student_in_range(
        self, student_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[PedagogicalObservation]:
        created_at_date = cast(PedagogicalObservationModel.created_at, SA_Date)
        stmt = select(PedagogicalObservationModel).where(
            PedagogicalObservationModel.student_id == student_id,
            created_at_date >= start_date,
            created_at_date <= end_date,
        )
        stmt = filter_as_of(stmt, created_at_date)
        models = self._session.execute(stmt).scalars().all()
        return [
            PedagogicalObservation(
                id=model.id,
                student_id=model.student_id,
                author_user_id=model.author_user_id,
                text=model.text,
                created_at=model.created_at,
            )
            for model in models
        ]

    def get_by_ids(self, ids: list[uuid.UUID]) -> list[PedagogicalObservation]:
        """Story 3.4 — batch resolution of `TrajectoryChangeSource.source_id`
        rows for the evidence card (RNF-11)."""
        if not ids:
            return []
        created_at_date = cast(PedagogicalObservationModel.created_at, SA_Date)
        stmt = select(PedagogicalObservationModel).where(PedagogicalObservationModel.id.in_(ids))
        stmt = filter_as_of(stmt, created_at_date)
        models = self._session.execute(stmt).scalars().all()
        return [
            PedagogicalObservation(
                id=model.id,
                student_id=model.student_id,
                author_user_id=model.author_user_id,
                text=model.text,
                created_at=model.created_at,
            )
            for model in models
        ]
