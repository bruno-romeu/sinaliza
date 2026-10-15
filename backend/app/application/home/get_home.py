"""`GetHomeService` — the only application-layer entry point for `GET /home`
(spec-3-3 Boundaries & Constraints).

Reads the already-committed `TrajectoryChange` rows via
`TrajectoryChangeRepositoryPort.list_recent` (capped at
`RECENT_CHANGES_LIMIT`, ordered by `detected_at` desc by the repository
itself) — this service never iterates students or triggers
`GetStudentTrajectoryService` recomputation; that stays request-scoped to the
per-student trajectory endpoint.

Each `TrajectoryChange` only carries `student_id`, so this service resolves
the display name via `StudentRepositoryPort.get_by_id` — the same
`EVAL_DEMO`-filtered lookup every other student-facing read uses (AD-11). A
`TrajectoryChange` is only ever written for an `EVAL_DEMO` student by
construction, but a row is skipped defensively (never raised) if that lookup
ever comes back empty, rather than crash the whole Home read over one bad
row.

spec-4-5 extends this service to also read every `FollowUp` whose status is
not `ENCERRADO` via `FollowUpRepositoryPort.list_active` (never capped — see
that port's docstring) — the same `student_name` resolution/skip-if-`None`
pattern is reused for these rows.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.home.ports import (
    FollowUpRepositoryPort,
    StudentRepositoryPort,
    TrajectoryChangeRepositoryPort,
)
from app.domain.follow_up import FollowUp
from app.domain.trajectory_change import TrajectoryChange

RECENT_CHANGES_LIMIT = 20


@dataclass(frozen=True)
class RecentChange:
    trajectory_change: TrajectoryChange
    student_name: str


@dataclass(frozen=True)
class ActiveFollowUp:
    follow_up: FollowUp
    student_name: str


@dataclass(frozen=True)
class HomeResult:
    recent_changes: list[RecentChange]
    active_follow_ups: list[ActiveFollowUp]


class GetHomeService:
    def __init__(
        self,
        trajectory_change_repository: TrajectoryChangeRepositoryPort,
        student_repository: StudentRepositoryPort,
        follow_up_repository: FollowUpRepositoryPort,
    ) -> None:
        self._trajectory_change_repository = trajectory_change_repository
        self._student_repository = student_repository
        self._follow_up_repository = follow_up_repository

    def execute(self) -> HomeResult:
        changes = self._trajectory_change_repository.list_recent(RECENT_CHANGES_LIMIT)

        recent_changes: list[RecentChange] = []
        for change in changes:
            student = self._student_repository.get_by_id(change.student_id)
            if student is None:
                continue
            recent_changes.append(RecentChange(trajectory_change=change, student_name=student.name))

        follow_ups = self._follow_up_repository.list_active()

        active_follow_ups: list[ActiveFollowUp] = []
        for follow_up in follow_ups:
            student = self._student_repository.get_by_id(follow_up.student_id)
            if student is None:
                continue
            active_follow_ups.append(ActiveFollowUp(follow_up=follow_up, student_name=student.name))

        return HomeResult(recent_changes=recent_changes, active_follow_ups=active_follow_ups)
