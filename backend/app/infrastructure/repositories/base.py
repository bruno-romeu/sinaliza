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

`utc_date_of` / `filter_as_of_timestamp` close the same gap for `timestamptz`
columns: the `cast(ts, Date)` idiom that `list_recent`/`count_recent`
(`TrajectoryChange.detected_at`) and `list_by_student_in_range`/`get_by_ids`
(`PedagogicalObservation.created_at`) each spelled out inline buckets a
timestamp into a day *at the Postgres session's `timezone` GUC*, not at UTC
— so the same row could land on either side of a day boundary depending on
a connection setting nothing in this codebase controls, while every other
date in the system (native `Date` columns, `as_of()`, `detected_at`
derivation) is UTC. These two helpers are now the only place that
conversion is written, and they pin it to UTC explicitly.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, Select, cast, func
from sqlalchemy import Date as SA_Date

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


def utc_date_of(timestamp_column: ColumnElement) -> ColumnElement:
    """The calendar date a `timestamptz` column falls on **in UTC**, as
    `timezone('UTC', col)::date`.

    A plain `cast(col, Date)` would instead resolve the day boundary at the
    session's `timezone` GUC — e.g. a `PedagogicalObservation` created at
    2026-09-24T23:30Z buckets as 2026-09-24 under a UTC session but as
    2026-09-24T20:30 → 2026-09-24 under `America/Sao_Paulo`, and an
    observation at 2026-09-25T02:00Z buckets as 09-25 under UTC but 09-24
    under `America/Sao_Paulo`. That silently shifts both the período
    bucketing behind the PEDAGOGICAL_OBSERVATION convergence signal and the
    `as_of()` truncation boundary, depending on a connection setting no code
    here sets. `AT TIME ZONE 'UTC'` makes the result independent of it.
    """
    return cast(func.timezone("UTC", timestamp_column), SA_Date)


def filter_as_of_timestamp(stmt: Select, timestamp_column: ColumnElement) -> Select:
    """`filter_as_of` for a `timestamptz` column — truncates to rows whose
    UTC calendar date is on or before `as_of()`."""
    return filter_as_of(stmt, utc_date_of(timestamp_column))
