"""Ports (interfaces) the `application/home` layer depends on.

`application/` only ever sees these Protocols — never a concrete class from
`infrastructure/` (AD-2). One narrow port per method actually used
(`application/trajectory/ports.py`'s convention): `GetHomeService` only ever
needs `list_recent`/`get_by_id`, `SearchStudentsService` only ever needs
`search` — neither widens an existing port to get there.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from app.domain.follow_up import FollowUp
from app.domain.student import Student, StudentSearchResult
from app.domain.trajectory_change import TrajectoryChange


class TrajectoryChangeRepositoryPort(Protocol):
    def list_recent(self, limit: int) -> list[TrajectoryChange]: ...


class FollowUpRepositoryPort(Protocol):
    def list_active(self, limit: int, offset: int) -> list[FollowUp]: ...
    def count_active(self) -> int: ...


class StudentRepositoryPort(Protocol):
    def get_by_id(self, student_id: uuid.UUID) -> Student | None: ...


class StudentSearchRepositoryPort(Protocol):
    def search(self, query: str, limit: int, offset: int) -> list[StudentSearchResult]: ...
    def count_matches(self, query: str) -> int: ...
