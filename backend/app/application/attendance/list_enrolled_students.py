"""`ListEnrolledStudentsService` — lists every student enrolled in a given
classroom (`EVAL_DEMO` split only, via the repository-base filter, AD-11)."""

from __future__ import annotations

import uuid

from app.application.attendance.errors import ClassroomNotFoundError
from app.application.attendance.ports import ClassroomRepositoryPort, StudentRepositoryPort
from app.domain.student import Student


class ListEnrolledStudentsService:
    def __init__(
        self,
        classroom_repository: ClassroomRepositoryPort,
        student_repository: StudentRepositoryPort,
    ) -> None:
        self._classroom_repository = classroom_repository
        self._student_repository = student_repository

    def execute(self, classroom_id: uuid.UUID) -> list[Student]:
        classroom = self._classroom_repository.get_by_id(classroom_id)
        if classroom is None:
            raise ClassroomNotFoundError()

        return self._student_repository.list_enrolled(classroom_id)
