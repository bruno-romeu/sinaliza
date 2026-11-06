"""Domain model for `MLModelVersion` — pure Python, zero framework imports
(AD-2), matching `domain/follow_up.py`'s style.

One row per successful `python -m app.ml.train` run (spec-5-1, RF-17):
`version` is a unique, human-identifiable string and `artifact_path` points
at the single serialized sklearn `Pipeline` file (preprocessing fused with
the classifier, RNF-03) que `app/ml/predict.py` e `app/ml/evaluate.py` leem de
volta com `joblib.load` — nunca refazendo o preprocessing. Estava no futuro
("Story 5.2's inference loader will later read back") desde a spec-5-1; as duas
leitoras existem desde a 5.2 e a 5.3.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MLModelVersion:
    """`training_dataset_version`, `feature_schema_version` e `metrics` fecham
    os seis campos que o `AGENTS.md` §"Versionamento de modelo" exige (antes
    só quatro eram persistidos). São opcionais por um motivo específico, não
    por conveniência: uma linha gravada antes dessas colunas existirem não tem
    como saber qual dataset a treinou, e `metrics` só passa a existir quando
    `python -m app.ml.evaluate` roda — treinar e avaliar no mesmo conjunto é
    proibido, então a métrica nunca nasce junto com a versão."""

    id: uuid.UUID
    version: str
    artifact_path: str
    trained_at: datetime
    created_at: datetime
    training_dataset_version: str | None = None
    feature_schema_version: str | None = None
    metrics: dict[str, Any] | None = None
