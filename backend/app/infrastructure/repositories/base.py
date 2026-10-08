"""Repository-base pattern (AD-11) — read-side invariants (`dataset_split =
EVAL_DEMO`, `as_of()`, pedagogical-observation visibility) are meant to be
enforced by a single reusable place, never by convention repeated in every
new repository.

This story established that pattern with its first, deliberately minimal
instance: one helper applying the `Student.dataset_split = EVAL_DEMO`
default filter, reused by `SqlAlchemyStudentRepository`. Story 3.1 extends
this same module with `filter_as_of` — the `as_of()` truncation helper this
docstring already anticipated — rather than each new trajectory repository
inventing its own inline filter (spec Code Map: "fecha lacuna que
epic-3-context.md assumia já existir").
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, Select

from app.domain.as_of import as_of
from app.domain.student import DatasetSplit
from app.infrastructure.db.models import StudentModel


def filter_eval_demo_students(stmt: Select) -> Select:
    """Applies the default `Student.dataset_split = EVAL_DEMO` read filter
    (AD-4) to any SELECT already selecting/joined against `StudentModel`."""
    return stmt.where(StudentModel.dataset_split == DatasetSplit.EVAL_DEMO)


def filter_as_of(stmt: Select, date_column: ColumnElement) -> Select:
    """Truncates any SELECT to rows whose `date_column` is on or before
    `as_of()` (AD-5, AD-11) — the single reusable place that keeps every
    trajectory-facing read from ever seeing data past the demo's simulated
    "today", mirroring `filter_eval_demo_students`'s precedent for the
    `EVAL_DEMO` split."""
    return stmt.where(date_column <= as_of())
