"""Domain model for `Student` — pure Python, zero framework imports (AD-2).

`dataset_split` is decided at synthetic-generation time, never at query time
(AD-4). The web application's reads always filter `= EVAL_DEMO`; `TRAIN` is
only ever read by the offline `ml/train`/`ml/evaluate` CLIs (out of scope for
this story).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum


class DatasetSplit(str, Enum):
    TRAIN = "TRAIN"
    EVAL_DEMO = "EVAL_DEMO"


@dataclass(frozen=True)
class Student:
    id: uuid.UUID
    name: str
    dataset_split: DatasetSplit
