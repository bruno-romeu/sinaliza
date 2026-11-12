"""The error envelope: `{ "error": { "code", "message" } }` (Consistency
Conventions). This is registered for `AppError` — FastAPI/Pydantic's
default validation error handling for malformed request bodies (422) is left
untouched, per the spec's I/O Matrix ("Standard Pydantic validation, not the
auth envelope").

It is also registered for `IntegrityViolationError` (the application layer's
reading of a database integrity violation, see `application/integrity.py`)
and, as a last-resort backstop, for the repository-level
`RepositoryIntegrityError` itself. Before this, both escaped as an unhandled
500: PR #40 translated `IntegrityError` into typed repository errors but
nothing above the repository caught them, and PR #39's explicit `ondelete`
semantics (several `RESTRICT`) made that a genuinely reachable path rather
than a hypothetical one.

The backstop exists because the mapping must not depend on every current
*and future* write service remembering to wrap its repository call: a
service that forgets still answers in the envelope, not with a 500. Its
`code`/`message` are identical to the mapped path's, so a forgotten wrap is
invisible to a client — the difference is only that the service never got
the chance to give the violation a domain-specific meaning (as
`RegisterAttendanceService` does for a duplicate attendance).

A third backstop, added when the adversarial QA pass measured it
(`docs/spec-qa-adversarial.md`, D1/D2), covers `sqlalchemy.exc.DataError` —
SQLSTATE class 22, "data exception": the value sent is not representable in
the column's type. Two triggers were reachable from the HTTP boundary: a page
number with no upper bound, whose derived `OFFSET` overflowed `bigint`, and a
NUL byte in free text, which psycopg refuses outright. Both are now refused
earlier, by `le=` on the page `Query(...)` and by the NUL check in
`schemas/free_text.py`, so this handler is the same kind of guarantee the
`RepositoryIntegrityError` one is: the mapping must not depend on every
current *and future* route remembering the right bound. Every member of class
22 means "this request's value is unprocessable", so 422 is the whole family's
answer — there is no case in it where 500 would be the honest one.

No response body ever carries the constraint or table name. Those are real
diagnostics (kept on the exception, reachable from a traceback/log), but
putting them in an HTTP body would hand a client the physical schema.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError

from app.application.integrity import (
    DuplicateRecordError,
    IntegrityViolationError,
    InvalidRecordValueError,
    MissingRequiredValueError,
    ReferencedRecordMissingError,
    translate_repository_integrity_error,
)
from app.infrastructure.repositories.errors import RepositoryIntegrityError


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


# A violation of a referential/uniqueness rule is a conflict with the state
# the database is actually in (409); a violation of a value rule (CHECK /
# NOT NULL) is the request itself being unprocessable (422) — the same
# family as Pydantic's own 422 and as the existing `student_not_enrolled`
# row of the I/O Matrix.
_INTEGRITY_RESPONSES: dict[type[IntegrityViolationError], tuple[int, str, str]] = {
    ReferencedRecordMissingError: (
        409,
        "referenced_record_missing",
        "A operação referencia um registro que não existe mais, ou o registro "
        "não pode ser removido porque ainda é referenciado.",
    ),
    DuplicateRecordError: (
        409,
        "duplicate_record",
        "Já existe um registro equivalente.",
    ),
    InvalidRecordValueError: (
        422,
        "invalid_record_value",
        "Um dos valores enviados não é aceito para este registro.",
    ),
    MissingRequiredValueError: (
        422,
        "missing_required_value",
        "Um campo obrigatório deste registro não foi informado.",
    ),
}

_GENERIC_INTEGRITY_RESPONSE = (
    409,
    "integrity_violation",
    "A operação não pôde ser concluída porque violaria uma regra de integridade dos dados.",
)


def _envelope(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def integrity_response(exc: IntegrityViolationError) -> JSONResponse:
    """The envelope for an integrity violation — one table, so the mapped
    path and the backstop can never drift apart."""
    status_code, code, message = _INTEGRITY_RESPONSES.get(type(exc), _GENERIC_INTEGRITY_RESPONSE)
    return _envelope(status_code, code, message)


async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _envelope(exc.status_code, exc.code, exc.message)


async def _integrity_error_handler(request: Request, exc: IntegrityViolationError) -> JSONResponse:
    return integrity_response(exc)


async def _repository_integrity_error_handler(
    request: Request, exc: RepositoryIntegrityError
) -> JSONResponse:
    """Backstop for a write path that reached the router without being
    wrapped in `translating_repository_integrity_errors` — answers in the
    same envelope the wrapped path would have produced."""
    return integrity_response(translate_repository_integrity_error(exc))


async def _data_error_handler(request: Request, exc: DataError) -> JSONResponse:
    """Backstop for a value the database could not represent at all (SQLSTATE
    class 22) and that no field-level validation refused first. The message
    stays generic on purpose: the driver's own text names the column type and
    sometimes the value, which belongs in the log, not in a response body."""
    return _envelope(
        422,
        "invalid_value",
        "Um dos valores enviados não pôde ser processado.",
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(IntegrityViolationError, _integrity_error_handler)
    app.add_exception_handler(RepositoryIntegrityError, _repository_integrity_error_handler)
    app.add_exception_handler(DataError, _data_error_handler)
