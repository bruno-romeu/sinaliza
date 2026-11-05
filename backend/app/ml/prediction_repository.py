"""`PredictionRepository` — the only place offline scoring code reads
students (spec-5-2 Boundaries & Constraints, mirroring `TrainingRepository`'s
precedent, spec-5-1 AD-11).

Structurally separate from the web path: a different module than
`infrastructure/repositories/`, no shared base class or mixin with
`SqlAlchemyStudentRepository`, and it filters `EVAL_DEMO` itself rather than
calling `filter_eval_demo_students`/`filter_as_of` from
`infrastructure/repositories/base.py` — those are the wrong filters here:
this reads the full `EVAL_DEMO` cut with no `as_of()` truncation (same
rationale as `ml/evaluate`, Story 5.3: this is offline research tooling, not
the live-demo path).

Reads every `StudentModel` row with `dataset_split == EVAL_DEMO` via the
shared `feature_aggregation.fetch_feature_rows()` helper (spec-5-3 — the
single source of truth also used by `TrainingRepository`/
`EvaluationRepository`), reusing `FEATURE_COLUMNS` so feature ordering never
drifts between training and scoring. Unlike `TrainingRepository`, there is no
label and no label-based exclusion: every `EVAL_DEMO` student is scored,
including one with no rows in a fact table (`None`/`0` features, same
null-handling as training's `SimpleImputer`)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domain.student import DatasetSplit
from app.ml.feature_aggregation import fetch_feature_rows, require_feature_fields

#: Reused directly from training (not redefined here) so scoring's feature
#: vectors line up with what the pipeline was fit on (spec Code Map).
# `app/ml/predict.py` imports this from `training_repository` directly.
from app.ml.training_repository import FEATURE_COLUMNS

__all__ = ["FEATURE_COLUMNS", "PredictionRepository", "ScoringRow"]


@dataclass(frozen=True)
class ScoringRow:
    """One `EVAL_DEMO` student's feature vector, ready for `app/ml/predict.py`
    to assemble into a feature matrix and score via the loaded `Pipeline`.
    Same null-handling convention as `TrainingRepository.TrainingRow`: rate
    features are `None` when the student has no rows in the corresponding
    fact table, `observation_count` is `0` in that case."""

    student_id: uuid.UUID
    attendance_rate: float | None
    grade_average: float | None
    assignment_completion_rate: float | None
    observation_count: int


#: `ScoringRow`'s field *order* no longer has to match `FEATURE_COLUMNS`:
#: `app/ml/predict.py` builds its matrix through `feature_vector()`, which
#: reads the columns by name in `FEATURE_COLUMNS` order, so a reorder there
#: reorders the matrix with it. What still has to hold is that every declared
#: feature exists as a field here — a rename on one side only would otherwise
#: surface as an `AttributeError` deep inside matrix construction. The
#: previous hardcoded tuple comparison was replaced by this structural check
#: because it also forbade ever adding a fifth feature (epic-5-retro-item-1).
require_feature_fields(ScoringRow)


class PredictionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def fetch_scoring_rows(self) -> list[ScoringRow]:
        feature_rows = fetch_feature_rows(self._session, DatasetSplit.EVAL_DEMO)
        return [
            ScoringRow(
                student_id=row.student_id,
                attendance_rate=row.attendance_rate,
                grade_average=row.grade_average,
                assignment_completion_rate=row.assignment_completion_rate,
                observation_count=row.observation_count,
            )
            for row in feature_rows
        ]
