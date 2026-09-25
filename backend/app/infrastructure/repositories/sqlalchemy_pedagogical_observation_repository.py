"""Implements `PedagogicalObservationRepositoryPort` on top of SQLAlchemy.

`save` never needs to translate an `IntegrityError` into a domain error —
`pedagogical_observations` carries no UNIQUE constraint (spec Boundaries &
Constraints: multiple observations for the same student are expected and
valid, each a new row, same precedent as `Grade`/`AssignmentSubmission`)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.pedagogical_observation import PedagogicalObservation
from app.infrastructure.db.models import PedagogicalObservationModel


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
