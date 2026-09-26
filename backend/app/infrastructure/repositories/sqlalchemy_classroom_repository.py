"""Implements `ClassroomRepositoryPort` on top of SQLAlchemy."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.classroom import Classroom
from app.infrastructure.db.models import ClassroomModel


def _to_domain(model: ClassroomModel) -> Classroom:
    return Classroom(id=model.id, name=model.name, academic_year=model.academic_year)


class SqlAlchemyClassroomRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[Classroom]:
        stmt = select(ClassroomModel).order_by(ClassroomModel.name)
        models = self._session.execute(stmt).scalars().all()
        return [_to_domain(model) for model in models]

    def get_by_id(self, classroom_id: uuid.UUID) -> Classroom | None:
        model = self._session.get(ClassroomModel, classroom_id)
        if model is None:
            return None
        return _to_domain(model)
