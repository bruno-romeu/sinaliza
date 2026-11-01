"""Application-layer meaning for a database integrity violation.

PR #40 stopped `IntegrityError` at the repository boundary: every write path
now goes through `infrastructure/repositories/errors.translating_integrity_errors`,
which rolls the session back and re-raises a typed
`RepositoryIntegrityError` subclass naming the violated class of constraint.
The translation stopped there, though — nothing above the repository caught
those, so a foreign-key violation still escaped the router as an unhandled
500 instead of a controlled response in the project's error envelope.

PR #39 made that reachable rather than hypothetical: 24 foreign keys now
declare explicit `ondelete` semantics, several of them `RESTRICT`. And even
without a delete flow, the *insert* side is already reachable today — the
bearer token is stateless and validated without a DB round trip
(`presentation/auth/dependencies.py`), so a token issued to a user whose row
was removed still authenticates, and the next
`POST /pedagogical-observations` / `POST /follow-ups/{id}/actions` writes an
`author_user_id` that no longer exists.

This module is the application layer's half of closing that: write services
wrap their repository call in `translating_repository_integrity_errors()`,
which re-raises the infrastructure-shaped exception as one of the four
intent-carrying errors below. `presentation/errors.py` maps those onto HTTP
status codes and the `{"error": {"code", "message"}}` envelope.

Why these errors live here and not in `domain/`
-----------------------------------------------
They are not school facts — they carry no pedagogical meaning at all
(AGENTS.md, "Separação de responsabilidades"). They say only "the database
refused this write, and this is the class of rule it broke", which is
exactly an application-service concern.

On importing `infrastructure.repositories.errors` from here
-----------------------------------------------------------
Deliberate, and narrower than what it replaces: `RegisterAttendanceService`
already imported `sqlalchemy.exc.IntegrityError` directly, so the
application layer was coupled to the persistence library *and* to its
least-specific exception. Catching the repository's own typed subclasses
instead keeps the coupling in one module (this one) and makes it precise.
`constraint_name`/`table_name` are carried through for diagnostics only —
they are never put in an HTTP response body, which would leak the physical
schema to a client (AGENTS.md, "Privacidade": a resposta expõe só o que o
acompanhamento precisa).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from app.infrastructure.repositories.errors import (
    CheckViolationError,
    ForeignKeyViolationError,
    NotNullViolationError,
    RepositoryIntegrityError,
    UniqueViolationError,
)


class IntegrityViolationError(Exception):
    """A write the database refused on an integrity rule.

    `constraint_name`/`table_name` are whatever Postgres reported (either
    may be `None`); `__cause__` is always the original
    `RepositoryIntegrityError`, so the source of the signal is never
    discarded (AGENTS.md, "Evidência").
    """

    def __init__(self, constraint_name: str | None = None, table_name: str | None = None) -> None:
        super().__init__(constraint_name or self.__class__.__name__)
        self.constraint_name = constraint_name
        self.table_name = table_name


class ReferencedRecordMissingError(IntegrityViolationError):
    """A FOREIGN KEY rejected the write: the row this write references does
    not exist, or something still references the row being removed
    (`ondelete=RESTRICT`)."""


class DuplicateRecordError(IntegrityViolationError):
    """A UNIQUE/exclusion constraint rejected the write — the row already
    exists."""


class InvalidRecordValueError(IntegrityViolationError):
    """A CHECK constraint rejected a written value (e.g.
    `ck_grade_value_range`)."""


class MissingRequiredValueError(IntegrityViolationError):
    """A NOT NULL column was written as `NULL`."""


_RepositoryToApplication = tuple[type[RepositoryIntegrityError], type[IntegrityViolationError]]

_BY_REPOSITORY_ERROR: tuple[_RepositoryToApplication, ...] = (
    (ForeignKeyViolationError, ReferencedRecordMissingError),
    (UniqueViolationError, DuplicateRecordError),
    (CheckViolationError, InvalidRecordValueError),
    (NotNullViolationError, MissingRequiredValueError),
)


def translate_repository_integrity_error(
    exc: RepositoryIntegrityError,
) -> IntegrityViolationError:
    """Maps a repository-level integrity error onto its application-level
    counterpart, keeping the constraint diagnostics. An unrecognised
    subclass falls back to the base `IntegrityViolationError` rather than
    being swallowed."""
    for repository_error, application_error in _BY_REPOSITORY_ERROR:
        if isinstance(exc, repository_error):
            return application_error(constraint_name=exc.constraint_name, table_name=exc.table_name)
    return IntegrityViolationError(constraint_name=exc.constraint_name, table_name=exc.table_name)


@contextmanager
def translating_repository_integrity_errors() -> Iterator[None]:
    """Wraps a write service's repository call so an integrity violation
    leaves the application layer as an `IntegrityViolationError`, never as
    an infrastructure exception the router cannot branch on.

    The session rollback already happened one layer down (see
    `infrastructure/repositories/errors.translating_integrity_errors`), so
    this only re-labels; it never touches the session.
    """
    try:
        yield
    except RepositoryIntegrityError as exc:
        raise translate_repository_integrity_error(exc) from exc
