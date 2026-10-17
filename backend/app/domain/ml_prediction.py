"""Domain model for `MLPrediction` — pure Python, zero framework imports
(AD-2), matching `domain/ml_model_version.py`'s style.

One row per scored `EVAL_DEMO` student per `python -m app.ml.predict` run
(spec-5-2). `score` is `1 - predict_proba(STABLE)` from the `MLModelVersion`
identified by `model_version_id` — the model's probability that the
student's trajectory does *not* belong to the `STABLE` profile. Re-running
the CLI is append-only: nothing here dedupes or skips an already-scored
student (spec Never), so `model_version_id` is how a later consumer learns
which run produced which row.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MLPrediction:
    id: uuid.UUID
    student_id: uuid.UUID
    model_version_id: uuid.UUID
    score: float
    created_at: datetime
