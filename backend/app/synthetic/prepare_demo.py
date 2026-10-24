"""Prepare the live demonstration — `python -m app.synthetic.prepare_demo`
(spec-ui-3).

`TrajectoryChange` rows are computed synchronously inside the request that
reads a student's trajectory (AD-1, epic-3-context.md), and `GET /home` only
reads rows that already exist. On a freshly generated base the Home is
therefore empty until someone opens each trajectory. This command opens all
of them once, through the exact same `GetStudentTrajectoryService` the
endpoint uses, so the Home reflects the base before a demo.

A one-off human action, run by hand after `app.synthetic.generate` (and with
the same `SINALIZA_DEMO_AS_OF` the demo will use). Never wire it into a cron,
timer or startup hook: that would be the background job AD-1/RNF-06 forbid.
"""

from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.composition import get_get_student_trajectory_service
from app.config import get_settings
from app.domain.as_of import as_of
from app.domain.student import DatasetSplit
from app.infrastructure.db.base import SessionLocal
from app.infrastructure.db.models import StudentModel


def prepare_demo(session: Session, window_days: int | None = None) -> tuple[int, int]:
    """Computes every `EVAL_DEMO` student's trajectory once. Returns
    `(students, changes)`: how many trajectories were computed and how many
    of them have a detected change."""
    window = window_days if window_days is not None else get_settings().trajectory_window_days
    service = get_get_student_trajectory_service(session)
    student_ids = session.execute(
        select(StudentModel.id)
        .where(StudentModel.dataset_split == DatasetSplit.EVAL_DEMO)
        .order_by(StudentModel.id)
    ).scalars().all()

    changes = 0
    for student_id in student_ids:
        result = service.execute(student_id, window)
        if result.trajectory_change is not None:
            changes += 1
    return len(student_ids), changes


def main() -> int:
    with SessionLocal() as session:
        students, changes = prepare_demo(session)
    print(
        f"Trajetórias calculadas para {students} estudantes em {as_of():%d/%m/%Y}: "
        f"{changes} com mudança detectada."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
