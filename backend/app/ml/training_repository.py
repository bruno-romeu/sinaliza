"""`TrainingRepository` — the only place offline training code reads
students (spec-5-1 Boundaries & Constraints, AD-11).

Structurally separate from the web path: a different module than
`infrastructure/repositories/`, no shared base class or mixin with
`SqlAlchemyStudentRepository`, and it never calls
`filter_eval_demo_students`/`filter_as_of` from
`infrastructure/repositories/base.py` — those enforce the `EVAL_DEMO`/
`as_of()` invariants the web path needs, and are structurally the wrong
filter for a repository whose entire purpose is reading the opposite split.

Reads only `StudentModel` rows with `dataset_split == TRAIN` and a non-null
`synthetic_profile` label (a `TRAIN` row with no label is simply excluded,
per the spec I/O Matrix — not an error on its own), joined with per-student
aggregates over attendance/grade/assignment/pedagogical-observation facts as
features. A student with no rows in one of those fact tables gets `None` for
that feature (`build_pipeline()`'s `SimpleImputer` fills it in at fit time)
rather than being excluded — only a missing *label* excludes a row.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.domain.assignment_submission import AssignmentSubmissionStatus
from app.domain.attendance import AttendanceStatus
from app.domain.student import DatasetSplit, SyntheticProfile
from app.infrastructure.db.models import (
    AssignmentSubmissionModel,
    AttendanceRecordModel,
    GradeModel,
    PedagogicalObservationModel,
    StudentModel,
)

#: Order feeds `app/ml/train.py`'s feature matrix construction and
#: `build_pipeline()`'s column indices — keep the two in sync.
FEATURE_COLUMNS: tuple[str, ...] = (
    "attendance_rate",
    "grade_average",
    "assignment_completion_rate",
    "observation_count",
)


@dataclass(frozen=True)
class TrainingRow:
    """One student's feature vector + label, ready for `app/ml/train.py` to
    assemble into `X`/`y`. `attendance_rate`/`grade_average`/
    `assignment_completion_rate` are `None` when the student has no rows in
    the corresponding fact table; `observation_count` is `0` in that case
    (a count, not a rate — "no observations" is a real, meaningful value)."""

    student_id: uuid.UUID
    attendance_rate: float | None
    grade_average: float | None
    assignment_completion_rate: float | None
    observation_count: int
    label: SyntheticProfile


class TrainingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def fetch_training_rows(self) -> list[TrainingRow]:
        students = self._session.execute(
            select(StudentModel.id, StudentModel.synthetic_profile)
            .where(StudentModel.dataset_split == DatasetSplit.TRAIN)
            .where(StudentModel.synthetic_profile.isnot(None))
        ).all()
        if not students:
            return []

        student_ids = [student.id for student in students]

        attendance_by_student = {
            row.student_id: (row.present, row.total)
            for row in self._session.execute(
                select(
                    AttendanceRecordModel.student_id,
                    func.count(AttendanceRecordModel.id).label("total"),
                    func.sum(
                        case((AttendanceRecordModel.status == AttendanceStatus.PRESENT, 1), else_=0)
                    ).label("present"),
                )
                .where(AttendanceRecordModel.student_id.in_(student_ids))
                .group_by(AttendanceRecordModel.student_id)
            ).all()
        }

        grade_average_by_student = {
            row.student_id: float(row.average)
            for row in self._session.execute(
                select(GradeModel.student_id, func.avg(GradeModel.value).label("average"))
                .where(GradeModel.student_id.in_(student_ids))
                .group_by(GradeModel.student_id)
            ).all()
        }

        submission_by_student = {
            row.student_id: (row.delivered, row.total)
            for row in self._session.execute(
                select(
                    AssignmentSubmissionModel.student_id,
                    func.count(AssignmentSubmissionModel.id).label("total"),
                    func.sum(
                        case(
                            (
                                AssignmentSubmissionModel.status
                                == AssignmentSubmissionStatus.DELIVERED,
                                1,
                            ),
                            else_=0,
                        )
                    ).label("delivered"),
                )
                .where(AssignmentSubmissionModel.student_id.in_(student_ids))
                .group_by(AssignmentSubmissionModel.student_id)
            ).all()
        }

        observation_count_by_student = {
            row.student_id: row.total
            for row in self._session.execute(
                select(
                    PedagogicalObservationModel.student_id,
                    func.count(PedagogicalObservationModel.id).label("total"),
                )
                .where(PedagogicalObservationModel.student_id.in_(student_ids))
                .group_by(PedagogicalObservationModel.student_id)
            ).all()
        }

        rows: list[TrainingRow] = []
        for student in students:
            present, total = attendance_by_student.get(student.id, (0, 0))
            attendance_rate = (present / total) if total else None

            delivered, submission_total = submission_by_student.get(student.id, (0, 0))
            assignment_completion_rate = (delivered / submission_total) if submission_total else None

            rows.append(
                TrainingRow(
                    student_id=student.id,
                    attendance_rate=attendance_rate,
                    grade_average=grade_average_by_student.get(student.id),
                    assignment_completion_rate=assignment_completion_rate,
                    observation_count=observation_count_by_student.get(student.id, 0),
                    label=student.synthetic_profile,
                )
            )
        return rows
