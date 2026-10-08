"""Implements `AssignmentRepositoryPort` on top of SQLAlchemy.

`save` never needs to translate an `IntegrityError` into a domain error —
`assignments` carries no UNIQUE constraint beyond FK integrity (spec
Boundaries & Constraints), mirrors `SqlAlchemyGradeRepository`'s precedent.

`list_due_in_range_for_student` (Story 3.1) joins through `EnrollmentModel`
— `Assignment` is classroom-scoped, not student-scoped, so "this student's
assignments" means "assignments of the classroom(s) this student is
enrolled in" — and applies `filter_as_of` on `due_date` (AD-11) so a
miscomputed range can never leak a not-yet-due assignment past `as_of()`.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.assignment import Assignment
from app.infrastructure.db.models import AssignmentModel, EnrollmentModel
from app.infrastructure.repositories.base import filter_as_of


def _to_domain(model: AssignmentModel) -> Assignment:
    return Assignment(
        id=model.id,
        classroom_id=model.classroom_id,
        subject=model.subject,
        period_id=model.period_id,
        due_date=model.due_date,
    )


class SqlAlchemyAssignmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        classroom_id: uuid.UUID,
        subject: str,
        period_id: uuid.UUID,
        due_date: date,
    ) -> Assignment:
        model = AssignmentModel(
            classroom_id=classroom_id,
            subject=subject,
            period_id=period_id,
            due_date=due_date,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return _to_domain(model)

    def get_by_id(self, assignment_id: uuid.UUID) -> Assignment | None:
        model = self._session.get(AssignmentModel, assignment_id)
        if model is None:
            return None
        return _to_domain(model)

    def list_by_classroom(self, classroom_id: uuid.UUID) -> list[Assignment]:
        stmt = (
            select(AssignmentModel)
            .where(AssignmentModel.classroom_id == classroom_id)
            .order_by(AssignmentModel.due_date)
        )
        models = self._session.execute(stmt).scalars().all()
        return [_to_domain(model) for model in models]

    def list_due_in_range_for_student(
        self, student_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[Assignment]:
        stmt = (
            select(AssignmentModel)
            .join(EnrollmentModel, EnrollmentModel.classroom_id == AssignmentModel.classroom_id)
            .where(
                EnrollmentModel.student_id == student_id,
                AssignmentModel.due_date >= start_date,
                AssignmentModel.due_date <= end_date,
            )
        )
        stmt = filter_as_of(stmt, AssignmentModel.due_date)
        models = self._session.execute(stmt).scalars().all()
        return [_to_domain(model) for model in models]
