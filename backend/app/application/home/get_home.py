"""`GetHomeService` — the only application-layer entry point for `GET /home`
(spec-3-3 Boundaries & Constraints).

Reads the already-committed `TrajectoryChange` rows via
`TrajectoryChangeRepositoryPort.list_recent` (ordered by `detected_at` desc
by the repository itself; paginated by `changes_page`/`changes_page_size`
since spec-ui-4 — a fixed cap of 5 had left every other change unreachable
from the Home) — this service never iterates students or triggers
`GetStudentTrajectoryService` recomputation; that stays request-scoped to the
per-student trajectory endpoint.

Each `TrajectoryChange` only carries `student_id`, so this service resolves
the display name via `StudentNameRepositoryPort.get_names_by_ids` — the same
`EVAL_DEMO`-filtered lookup every other student-facing read uses (AD-11),
asked for the whole page in **one** query. A `TrajectoryChange` is only ever
written for an `EVAL_DEMO` student by construction, but a row is skipped
defensively (never raised) if that lookup ever comes back empty, rather than
crash the whole Home read over one bad row — an id absent from the returned
mapping is exactly the old `get_by_id(...) is None`.

That resolution used to be a `get_by_id` call *inside* each of the two loops
below, which made the Home's query count `4 + N + M` — linear in two page
sizes the client controls, up to 100 each (`MAX_CHANGES_PAGE_SIZE`/
`MAX_FOLLOW_UPS_PAGE_SIZE`). Measured against a copy of the demo database: 10
queries at the default 5+5 and 21 at 100/100, against 6 constant now. With
~200 synthetic students even 204 queries finish in milliseconds, so this was
never *slow* — it was a count that grows with data the demo does not have yet,
which is why it is closed by batching and not by caching (`AGENTS.md`
§Atalhos proibidos: nenhuma tecnologia nova).

spec-4-5 extends this service to also read every `FollowUp` whose status is
not `ENCERRADO` via `FollowUpRepositoryPort.list_active` — paginated by
`follow_ups_page`/`follow_ups_page_size` (1-indexed; `DEFAULT_FOLLOW_UPS_PAGE_SIZE`
matches the old fixed behavior's effective page-1 view) rather than the
originally-"never capped" list, since open-case volume grows without bound
over the life of a real deployment — the same `student_name`
resolution/skip-if-missing pattern is reused for these rows.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.home.ports import (
    FollowUpRepositoryPort,
    StudentNameRepositoryPort,
    TrajectoryChangeRepositoryPort,
)
from app.domain.follow_up import FollowUp
from app.domain.trajectory_change import TrajectoryChange

#: Tamanho de página padrão e teto aceito. Os dois `MAX_*` são o `le=` dos
#: `Query(...)` em `app/presentation/home/router.py`, que os importa daqui em
#: vez de repetir o literal `100` — era o que fazia até esta onda de higiene,
#: e o resultado era o número existir em dois lugares com só um deles dizendo
#: o que ele significa.
DEFAULT_CHANGES_PAGE_SIZE = 5
MAX_CHANGES_PAGE_SIZE = 100
DEFAULT_FOLLOW_UPS_PAGE_SIZE = 5
MAX_FOLLOW_UPS_PAGE_SIZE = 100


@dataclass(frozen=True)
class RecentChange:
    trajectory_change: TrajectoryChange
    student_name: str


@dataclass(frozen=True)
class ActiveFollowUp:
    follow_up: FollowUp
    student_name: str


@dataclass(frozen=True)
class ActiveFollowUpsPage:
    items: list[ActiveFollowUp]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class RecentChangesPage:
    items: list[RecentChange]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class HomeResult:
    recent_changes: RecentChangesPage
    active_follow_ups: ActiveFollowUpsPage


class GetHomeService:
    def __init__(
        self,
        trajectory_change_repository: TrajectoryChangeRepositoryPort,
        student_repository: StudentNameRepositoryPort,
        follow_up_repository: FollowUpRepositoryPort,
    ) -> None:
        self._trajectory_change_repository = trajectory_change_repository
        self._student_repository = student_repository
        self._follow_up_repository = follow_up_repository

    def execute(
        self,
        follow_ups_page: int = 1,
        follow_ups_page_size: int = DEFAULT_FOLLOW_UPS_PAGE_SIZE,
        changes_page: int = 1,
        changes_page_size: int = DEFAULT_CHANGES_PAGE_SIZE,
    ) -> HomeResult:
        total_changes = self._trajectory_change_repository.count_recent()
        changes = self._trajectory_change_repository.list_recent(
            changes_page_size, (changes_page - 1) * changes_page_size
        )

        change_names = self._student_repository.get_names_by_ids(
            [change.student_id for change in changes]
        )
        recent_changes: list[RecentChange] = []
        for change in changes:
            student_name = change_names.get(change.student_id)
            if student_name is None:
                continue
            recent_changes.append(RecentChange(trajectory_change=change, student_name=student_name))

        total_active_follow_ups = self._follow_up_repository.count_active()
        offset = (follow_ups_page - 1) * follow_ups_page_size
        follow_ups = self._follow_up_repository.list_active(follow_ups_page_size, offset)

        follow_up_names = self._student_repository.get_names_by_ids(
            [follow_up.student_id for follow_up in follow_ups]
        )
        active_follow_ups: list[ActiveFollowUp] = []
        for follow_up in follow_ups:
            student_name = follow_up_names.get(follow_up.student_id)
            if student_name is None:
                continue
            active_follow_ups.append(ActiveFollowUp(follow_up=follow_up, student_name=student_name))

        return HomeResult(
            recent_changes=RecentChangesPage(
                items=recent_changes,
                total=total_changes,
                page=changes_page,
                page_size=changes_page_size,
            ),
            active_follow_ups=ActiveFollowUpsPage(
                items=active_follow_ups,
                total=total_active_follow_ups,
                page=follow_ups_page,
                page_size=follow_ups_page_size,
            ),
        )
