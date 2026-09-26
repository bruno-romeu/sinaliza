"""Implements `AcademicPeriodRepositoryPort` on top of SQLAlchemy."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.academic_period import AcademicPeriod
from app.infrastructure.db.models import AcademicPeriodModel


def _to_domain(model: AcademicPeriodModel) -> AcademicPeriod:
    return AcademicPeriod(
        id=model.id,
        label=model.label,
        start_date=model.start_date,
        end_date=model.end_date,
        order_index=model.order_index,
    )


class SqlAlchemyAcademicPeriodRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[AcademicPeriod]:
        stmt = select(AcademicPeriodModel).order_by(AcademicPeriodModel.order_index)
        models = self._session.execute(stmt).scalars().all()
        return [_to_domain(model) for model in models]

    def get_by_id(self, period_id: uuid.UUID) -> AcademicPeriod | None:
        model = self._session.get(AcademicPeriodModel, period_id)
        if model is None:
            return None
        return _to_domain(model)
