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
`EVAL_DEMO` student unbounded.

The query is trimmed before being handed to the repository, so a trailing or
leading space (e.g. `"Ana "`) still matches a student literally named `"Ana"`
instead of silently failing to match.

Paginated by `page`/`page_size` (1-indexed, same convention as
`GetHomeService`'s follow-up pagination) — `total` (the true match count,
not just this page's length) is what makes paging past the first page
possible."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.home.ports import StudentSearchRepositoryPort
from app.domain.student import StudentSearchResult

DEFAULT_PAGE_SIZE = 5
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class StudentSearchPage:
    results: list[StudentSearchResult]
    total: int
    page: int
    page_size: int


class SearchStudentsService:
    def __init__(self, student_repository: StudentSearchRepositoryPort) -> None:
        self._student_repository = student_repository

    def execute(
        self, query: str, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
    ) -> StudentSearchPage:
        trimmed = query.strip()
        if not trimmed:
            return StudentSearchPage(results=[], total=0, page=page, page_size=page_size)

        total = self._student_repository.count_matches(trimmed)
        offset = (page - 1) * page_size
        results = self._student_repository.search(trimmed, page_size, offset)
        return StudentSearchPage(results=results, total=total, page=page, page_size=page_size)
