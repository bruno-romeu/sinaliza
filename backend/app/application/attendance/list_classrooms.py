"""`ListClassroomsService` — lists every dev-fixture classroom.

There is no classroom CRUD screen (spec Boundaries & Constraints);
classrooms only ever come from `seed_dev_fixtures.py`.
"""

from __future__ import annotations

from app.application.attendance.ports import ClassroomRepositoryPort
from app.domain.classroom import Classroom


class ListClassroomsService:
    def __init__(self, classroom_repository: ClassroomRepositoryPort) -> None:
        self._classroom_repository = classroom_repository

    def execute(self) -> list[Classroom]:
        return self._classroom_repository.list_all()
