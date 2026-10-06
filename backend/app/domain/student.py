"""Domain model for `Student` — pure Python, zero framework imports (AD-2).

`dataset_split` is decided at synthetic-generation time, never at query time
(AD-4). The web application's reads always filter `= EVAL_DEMO`; `TRAIN` is
only ever read by the offline `ml/train`/`ml/evaluate` CLIs (out of scope for
this story).

`SyntheticProfile` lives here because the ORM model and the Alembic migration
both need its values, but it is deliberately **not** a field on `Student`: it
is a research label that must never reach a product response schema (D2,
AD-3's boundary applied to the synthetic answer key). Leaving the field off
the product-facing dataclass makes that boundary structural instead of a
convention — no repository can carry the label into an application service,
because there is nowhere to put it. `StudentModel.synthetic_profile` is the
only in-code carrier. Story 2.1 ships the column NULL; Story 2.2 populates
it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum


class DatasetSplit(str, Enum):
    TRAIN = "TRAIN"
    EVAL_DEMO = "EVAL_DEMO"


class SyntheticProfile(str, Enum):
    """Named, documented trajectory rules applied by the synthetic generator
    (`data-model.md` §Geração sintética) — never opaque randomness. The set
    brackets the spectrum RF-11's convergence rule has to distinguish: one
    profile with no change at all, one combining attendance + grade +
    assignment deterioration."""

    STABLE = "STABLE"
    FALLING_ATTENDANCE = "FALLING_ATTENDANCE"
    COMBINED_DETERIORATION = "COMBINED_DETERIORATION"


@dataclass(frozen=True)
class Student:
    id: uuid.UUID
    name: str
    dataset_split: DatasetSplit
