"""Domain model for `MLModelVersion` — pure Python, zero framework imports
(AD-2), matching `domain/follow_up.py`'s style.

One row per successful `python -m app.ml.train` run (spec-5-1, RF-17):
`version` is a unique, human-identifiable string and `artifact_path` points
at the single serialized sklearn `Pipeline` file (preprocessing fused with
the classifier, RNF-03) Story 5.2's inference loader will later read back
with `joblib.load`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MLModelVersion:
    id: uuid.UUID
    version: str
    artifact_path: str
    trained_at: datetime
    created_at: datetime
