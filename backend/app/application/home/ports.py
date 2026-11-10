"""Ports (interfaces) the `application/home` layer depends on.

`application/` only ever sees these Protocols — never a concrete class from
`infrastructure/` (AD-2). One narrow port per method actually used
(`application/trajectory/ports.py`'s convention): `GetHomeService` only ever
needs `list_recent`/`get_names_by_ids`, `SearchStudentsService` only ever needs
`search` — neither widens an existing port to get there.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from app.domain.follow_up import FollowUp
from app.domain.student import StudentSearchResult
from app.domain.trajectory_change import TrajectoryChange


class TrajectoryChangeRepositoryPort(Protocol):
    def list_recent(self, limit: int, offset: int = 0) -> list[TrajectoryChange]: ...
    def count_recent(self) -> int: ...


class FollowUpRepositoryPort(Protocol):
    def list_active(self, limit: int, offset: int) -> list[FollowUp]: ...
    def count_active(self) -> int: ...


class StudentNameRepositoryPort(Protocol):
    """Batch name resolution — deliberately *not* `get_by_id`.

    `GetHomeService` used to call `get_by_id` once per listed row, so the
    Home's query count was `4 + N + M` in the two page sizes the client
    controls (up to 100 each). Measured against a copy of the demo database:
    10 queries at the default 5+5, 21 at `?changes_page_size=100&
    follow_ups_page_size=100` (21 and not 204 only because the dataset holds
    16 changes and 1 follow-up). The port asks for names in one call so the
    count stops depending on how many rows a page holds.
    """

    def get_names_by_ids(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]: ...


class StudentSearchRepositoryPort(Protocol):
    def search(self, query: str, limit: int, offset: int) -> list[StudentSearchResult]: ...
    def count_matches(self, query: str) -> int: ...
