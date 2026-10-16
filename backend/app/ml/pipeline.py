"""`build_pipeline()` — the single sklearn `Pipeline` (preprocessing fused
with the classifier) that `app/ml/train.py` fits and serializes, and that
inference must reuse verbatim later (RNF-03): never a separately
reimplemented preprocessing step.

Operates on a plain numeric feature matrix (column order matches
`training_repository.FEATURE_COLUMNS`), so the `ColumnTransformer` addresses
columns by index rather than by name — no pandas dependency needed for this
story's reasonable-not-exhaustive feature set (spec Design Notes).
"""

from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from app.ml.training_repository import FEATURE_COLUMNS

#: Derived from `training_repository.FEATURE_COLUMNS` so the two can never
#: silently desync.
_NUMERIC_FEATURE_COUNT = len(FEATURE_COLUMNS)


def build_pipeline() -> Pipeline:
    """Returns an unfitted `Pipeline`: a `ColumnTransformer` that mean-fills
    missing per-student aggregates (a student with no rows in some fact
    table yields `None` from `TrainingRepository`, spec I/O Matrix), feeding
    a `RandomForestClassifier` with a fixed `random_state` so training is
    deterministic across runs (spec Design Notes)."""
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", SimpleImputer(strategy="mean"), list(range(_NUMERIC_FEATURE_COUNT))),
        ]
    )
    classifier = RandomForestClassifier(n_estimators=100, random_state=42)
    return Pipeline(steps=[("preprocessor", preprocessor), ("classifier", classifier)])
