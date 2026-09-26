"""Implements `StudentRepositoryPort` on top of SQLAlchemy.

Both `list_enrolled` and `exists_enrollment` apply the `dataset_split =
EVAL_DEMO` default read filter via `repositories/base.py` (AD-11) — a
`TRAIN`-split student must never be treated as validly enrolled, whether for
listing or for an attendance write (spec Boundaries & Constraints).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.student import Student
from app.infrastructure.db.models import EnrollmentModel, StudentModel
from app.infrastructure.repositories.base import filter_eval_demo_students


class SqlAlchemyStudentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_enrolled(self, classroom_id: uuid.UUID) -> list[Student]:
        stmt = (
            select(StudentModel)
            .join(EnrollmentModel, EnrollmentModel.student_id == StudentModel.id)
            .where(EnrollmentModel.classroom_id == classroom_id)
            .order_by(StudentModel.name)
        )
        stmt = filter_eval_demo_students(stmt)
        models = self._session.execute(stmt).scalars().all()
        return [
            Student(id=model.id, name=model.name, dataset_split=model.dataset_split)
            for model in models
        ]

    def exists_enrollment(self, student_id: uuid.UUID, classroom_id: uuid.UUID) -> bool:
        exists_stmt = (
            select(StudentModel.id)
            .join(EnrollmentModel, EnrollmentModel.student_id == StudentModel.id)
            .where(
                EnrollmentModel.student_id == student_id,
                EnrollmentModel.classroom_id == classroom_id,
            )
        )
        exists_stmt = filter_eval_demo_students(exists_stmt)
        stmt = select(exists_stmt.exists())
        return bool(self._session.execute(stmt).scalar_one())
