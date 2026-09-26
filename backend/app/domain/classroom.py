"""Domain model for `Classroom` — pure Python, zero framework imports (AD-2).

`academic_year` is populated now (not deferred) because `data-model.md`
already fixes its shape — omitting it would just mean a backfill migration
once Epic 2 needs it (spec Design Notes).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Classroom:
    id: uuid.UUID
    name: str
    academic_year: int
