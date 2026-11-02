"""Typed translation of Postgres integrity violations, raised by every
repository write path instead of a bare `sqlalchemy.exc.IntegrityError`.

Why this exists
---------------
Until now only `SqlAlchemyAttendanceRepository.save` reacted to an
`IntegrityError` at all (rolling back and re-raising, so
`RegisterAttendanceService` could translate it into
`DuplicateAttendanceError`). Every other write path — grades, assignments,
submissions, pedagogical observations, follow-ups, trajectory changes — let
the raw driver exception escape *without rolling back*, which has two
consequences:

1. the caller gets an untyped, infrastructure-shaped exception it cannot
   reasonably branch on (which constraint failed? a UNIQUE? an FK?), so a
   violation surfaces as an unhandled 500 rather than a controlled response;
2. worse, the `Session` is left in the "deactivated transaction" state —
   every later statement on it raises `PendingRollbackError`, so a single
   failed write poisons whatever the caller does next (a real hazard in
   tests, which share one `db_session` across several requests, and in any
   request that writes more than once).

`translating_integrity_errors` closes both: it always rolls back, and it
re-raises a subclass naming the violated class of constraint, carrying the
constraint/table name reported by Postgres and chaining the original
exception (`__cause__`) — the source is never discarded (AGENTS.md,
"Evidência": nunca descartar a fonte original).

Why these no longer subclass `IntegrityError`
--------------------------------------------
They used to, transitionally: `RegisterAttendanceService` caught
`sqlalchemy.exc.IntegrityError` to raise `DuplicateAttendanceError`, so
subclassing meant translating at the repository changed no HTTP behaviour
while the application layer had not caught up yet.

PR #44 removed that last consumer — the service now catches
`DuplicateRecordError` (`application/integrity.py`), and every write path
is wrapped in `translating_repository_integrity_errors`. With no caller
depending on the driver type, these are plain exceptions again.

That matters beyond tidiness: while the inheritance stood, any
`except IntegrityError` anywhere would silently swallow an already-typed
repository error and re-wrap a rolled-back session's failure as if it were
a fresh driver exception. Tests that assert on a *raw* driver violation
(`test_attendance.py`, `test_grades.py`, `test_auth_login.py`,
`test_migrations.py`) go through `session.commit()`/`connection.execute()`
directly, never a repository, so they still observe the real
`sqlalchemy.exc.IntegrityError` and are unaffected.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# Postgres SQLSTATE class 23 — integrity constraint violation.
_UNIQUE_VIOLATION = "23505"
_FOREIGN_KEY_VIOLATION = "23503"
_NOT_NULL_VIOLATION = "23502"
_CHECK_VIOLATION = "23514"
_EXCLUSION_VIOLATION = "23P01"


class RepositoryIntegrityError(Exception):
    """A database integrity violation, translated at the repository boundary.

    `constraint_name`/`table_name` are whatever Postgres reported in the
    error's diagnostics (both may be `None` for a driver or error that does
    not carry them); `__cause__` is always the original `IntegrityError`.

    `statement`/`params`/`orig` are kept as plain attributes rather than
    dropped with the base class: they are the evidence trail back to the
    exact write that failed (AGENTS.md, "Evidência": nunca descartar a
    fonte original).
    """

    def __init__(
        self,
        statement: str | None,
        params: object,
        orig: BaseException,
        constraint_name: str | None = None,
        table_name: str | None = None,
    ) -> None:
        super().__init__(statement)
        self.statement = statement
        self.params = params
        self.orig = orig
        self.constraint_name = constraint_name
        self.table_name = table_name


class UniqueViolationError(RepositoryIntegrityError):
    """A UNIQUE/exclusion constraint rejected the write — the row already
    exists (SQLSTATE 23505/23P01)."""


class ForeignKeyViolationError(RepositoryIntegrityError):
    """A FOREIGN KEY constraint rejected the write — the row references (or
    is referenced by) something that does not exist (SQLSTATE 23503)."""


class NotNullViolationError(RepositoryIntegrityError):
    """A NOT NULL column was written as `NULL` (SQLSTATE 23502)."""


class CheckViolationError(RepositoryIntegrityError):
    """A CHECK constraint rejected the written value (SQLSTATE 23514) — e.g.
    `ck_grade_value_range`."""


_BY_SQLSTATE: dict[str, type[RepositoryIntegrityError]] = {
    _UNIQUE_VIOLATION: UniqueViolationError,
    _EXCLUSION_VIOLATION: UniqueViolationError,
    _FOREIGN_KEY_VIOLATION: ForeignKeyViolationError,
    _NOT_NULL_VIOLATION: NotNullViolationError,
    _CHECK_VIOLATION: CheckViolationError,
}


def _diagnostic(orig: BaseException | None, field: str) -> str | None:
    """Reads one field off psycopg's `Diagnostics` object, tolerating any
    driver that does not expose one."""
    diag = getattr(orig, "diag", None)
    value = getattr(diag, field, None)
    return value if isinstance(value, str) else None


def translate_integrity_error(exc: IntegrityError) -> RepositoryIntegrityError:
    """Maps `exc` onto the `RepositoryIntegrityError` subclass matching its
    SQLSTATE, keeping the statement/params/original exception intact. An
    already-translated error is returned unchanged, so wrapping a wrapped
    call never re-wraps."""
    if isinstance(exc, RepositoryIntegrityError):
        return exc

    orig = exc.orig
    sqlstate = getattr(orig, "sqlstate", None) or getattr(exc, "code", None)
    error_class = _BY_SQLSTATE.get(sqlstate or "", RepositoryIntegrityError)
    return error_class(
        exc.statement,
        exc.params,
        orig if orig is not None else exc,
        constraint_name=_diagnostic(orig, "constraint_name"),
        table_name=_diagnostic(orig, "table_name"),
    )


@contextmanager
def translating_integrity_errors(session: Session) -> Iterator[None]:
    """Wraps a repository write: on an integrity violation, rolls the session
    back (so it stays usable, see this module's docstring) and re-raises the
    typed translation, chained to the original.

    The `rollback()` is what puts the session back in a usable state — a
    failed flush/commit leaves its transaction merely *deactivated*, not
    actually rolled back yet.
    """
    try:
        yield
    except IntegrityError as exc:
        session.rollback()
        raise translate_integrity_error(exc) from exc
