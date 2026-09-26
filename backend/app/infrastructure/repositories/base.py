"""Repository-base pattern (AD-11) — read-side invariants (`dataset_split =
EVAL_DEMO`, `as_of()`, pedagogical-observation visibility) are meant to be
enforced by a single reusable place, never by convention repeated in every
new repository.

This story establishes that pattern with its first, deliberately minimal
instance: one helper applying the `Student.dataset_split = EVAL_DEMO`
default filter, reused by `SqlAlchemyStudentRepository`. Stories 1.3+ and
Epic 3 are expected to extend this same module (e.g. an `as_of()` helper,
a pedagogical-observation visibility helper) rather than each inventing
their own inline filter — see the spec's Design Notes.
"""

from __future__ import annotations

from sqlalchemy import Select

from app.domain.student import DatasetSplit
from app.infrastructure.db.models import StudentModel


def filter_eval_demo_students(stmt: Select) -> Select:
    """Applies the default `Student.dataset_split = EVAL_DEMO` read filter
    (AD-4) to any SELECT already selecting/joined against `StudentModel`."""
    return stmt.where(StudentModel.dataset_split == DatasetSplit.EVAL_DEMO)
