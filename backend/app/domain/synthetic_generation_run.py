"""Domain model for `SyntheticGenerationRun` — pure Python, zero framework
imports (AD-2).

The provenance record of one execution of the synthetic generator: which seed
produced the base, which generator version produced it, when, at what volume
and at what train/eval proportion. Without it the determinism claim of
RNF-13 is unverifiable after the fact — a base in the database would have no
way to say which invocation built it.

`train_ratio` is persisted per run (not read from a global constant) because
the proportion between the two recortes is a generation decision: a base
generated at a different proportion has to stay identifiable as such
(`data-model.md` §Geração sintética).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class SyntheticGenerationRun:
    id: uuid.UUID
    seed: int
    generator_version: str
    executed_at: datetime
    student_count: int
    train_ratio: Decimal
