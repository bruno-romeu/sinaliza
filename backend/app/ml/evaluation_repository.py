"""`EvaluationRepository` — the only place `python -m app.ml.evaluate` reads
students (spec-5-3 Boundaries & Constraints).

Structurally mirrors `PredictionRepository`: reads the complete `EVAL_DEMO`
cut via the shared `feature_aggregation.fetch_feature_rows()` helper, never
calls `filter_as_of`/`filter_eval_demo_students` from
`infrastructure/repositories/base.py` (those are the web path's invariants,
not offline research tooling's), and never truncates to any `as_of()`
"today" — unlike `PredictionRepository`, each row also carries the
student's `synthetic_profile` ground-truth label, so a student with no label
is excluded (there is nothing to score the model's prediction against).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.student import DatasetSplit, SyntheticProfile
from app.infrastructure.db.models import StudentModel
from app.ml.feature_aggregation import fetch_feature_rows


@dataclass(frozen=True)
class EvaluationRow:
    """One labeled `EVAL_DEMO` student's feature vector + ground-truth
    `synthetic_profile`, ready for `app/ml/evaluate.py` to assemble into
    `X`/`y_true`. Same null-handling convention as `TrainingRow`/`ScoringRow`:
    rate features are `None` when the student has no rows in the
    corresponding fact table, `observation_count` is `0` in that case."""

    student_id: uuid.UUID
    attendance_rate: float | None
    grade_average: float | None
    assignment_completion_rate: float | None
    observation_count: int
    label: SyntheticProfile


class EvaluationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def fetch_evaluation_rows(self) -> list[EvaluationRow]:
        feature_rows = fetch_feature_rows(self._session, DatasetSplit.EVAL_DEMO)
        if not feature_rows:
            return []

        student_ids = [row.student_id for row in feature_rows]
        labels_by_student = {
            row.id: row.synthetic_profile
            for row in self._session.execute(
                select(StudentModel.id, StudentModel.synthetic_profile).where(
                    StudentModel.id.in_(student_ids)
                )
            ).all()
            if row.synthetic_profile is not None
        }

        rows: list[EvaluationRow] = []
        for feature_row in feature_rows:
            label = labels_by_student.get(feature_row.student_id)
            if label is None:
                continue
            rows.append(
                EvaluationRow(
                    student_id=feature_row.student_id,
                    attendance_rate=feature_row.attendance_rate,
                    grade_average=feature_row.grade_average,
                    assignment_completion_rate=feature_row.assignment_completion_rate,
                    observation_count=feature_row.observation_count,
                    label=label,
                )
            )
        return rows
