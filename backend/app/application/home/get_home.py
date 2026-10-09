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
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.home.ports import StudentRepositoryPort, TrajectoryChangeRepositoryPort
from app.domain.trajectory_change import TrajectoryChange

RECENT_CHANGES_LIMIT = 20


@dataclass(frozen=True)
class RecentChange:
    trajectory_change: TrajectoryChange
    student_name: str


class GetHomeService:
    def __init__(
        self,
        trajectory_change_repository: TrajectoryChangeRepositoryPort,
        student_repository: StudentRepositoryPort,
    ) -> None:
        self._trajectory_change_repository = trajectory_change_repository
        self._student_repository = student_repository

    def execute(self) -> list[RecentChange]:
        changes = self._trajectory_change_repository.list_recent(RECENT_CHANGES_LIMIT)

        recent_changes: list[RecentChange] = []
        for change in changes:
            student = self._student_repository.get_by_id(change.student_id)
            if student is None:
                continue
            recent_changes.append(RecentChange(trajectory_change=change, student_name=student.name))
        return recent_changes
