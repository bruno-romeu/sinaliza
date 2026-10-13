"""Implements `StudentRepositoryPort` on top of SQLAlchemy.

`list_enrolled`, `exists_enrollment` and `get_by_id` all apply the
`dataset_split = EVAL_DEMO` default read filter via `repositories/base.py`
(AD-11) — a `TRAIN`-split student must never be treated as validly enrolled,
whether for listing, an attendance write, or `GET /students/{id}/trajectory`
(spec Boundaries & Constraints: "estudante inexistente ou TRAIN → mesmo 404,
nunca vaza o split")."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.student import Student, StudentSearchResult
from app.infrastructure.db.models import ClassroomModel, EnrollmentModel, StudentModel
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

    def get_by_id(self, student_id: uuid.UUID) -> Student | None:
        stmt = select(StudentModel).where(StudentModel.id == student_id)
        stmt = filter_eval_demo_students(stmt)
        model = self._session.execute(stmt).scalar_one_or_none()
        if model is None:
            return None
        return Student(id=model.id, name=model.name, dataset_split=model.dataset_split)

    def search(self, query: str, limit: int) -> list[StudentSearchResult]:
        """Home's student search (spec-3-3 Boundaries & Constraints):
        case-insensitive (`ILIKE`) match on either `StudentModel.name` or the
        joined `ClassroomModel.name`, scoped to `filter_eval_demo_students`
        (AD-11), same as every other student-facing read.

        Capped at `limit` rows (decision: same 20-row cap as `list_recent`,
        no "showing N of M" count indicator) so a short query can't return
        the entire matching `EVAL_DEMO` roster unbounded."""
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        stmt = (
            select(StudentModel, ClassroomModel.name)
            .join(EnrollmentModel, EnrollmentModel.student_id == StudentModel.id)
            .join(ClassroomModel, ClassroomModel.id == EnrollmentModel.classroom_id)
            .where(
                or_(
                    StudentModel.name.ilike(pattern, escape="\\"),
                    ClassroomModel.name.ilike(pattern, escape="\\"),
                )
            )
            .order_by(StudentModel.name)
            .limit(limit)
        )
        stmt = filter_eval_demo_students(stmt)
        rows = self._session.execute(stmt).all()
        return [
            StudentSearchResult(id=student.id, name=student.name, classroom_name=classroom_name)
            for student, classroom_name in rows
        ]
