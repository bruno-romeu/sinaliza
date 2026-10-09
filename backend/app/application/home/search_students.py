"""`SearchStudentsService` — the only application-layer entry point for `GET
/home/search` (spec-3-3 Boundaries & Constraints).

A thin pass-through over `StudentSearchRepositoryPort.search`: the
`EVAL_DEMO` filter and the name/classroom `ILIKE` matching both live in the
repository (AD-11, mirrors every other student-facing read), so there is
nothing left for this service to add beyond the layering boundary itself
(`presentation/` never calls `infrastructure/` directly, AD-2). No "not
found" error case — an empty match is a normal, successful result (spec I/O
Matrix: "Search no match... Empty results array").

A blank/whitespace-only query short-circuits to an empty result before ever
reaching the repository: `ILIKE '%%'` would otherwise match every
`EVAL_DEMO` student unbounded."""

from __future__ import annotations

from app.application.home.ports import StudentSearchRepositoryPort
from app.domain.student import StudentSearchResult


class SearchStudentsService:
    def __init__(self, student_repository: StudentSearchRepositoryPort) -> None:
        self._student_repository = student_repository

    def execute(self, query: str) -> list[StudentSearchResult]:
        if not query.strip():
            return []
        return self._student_repository.search(query)
