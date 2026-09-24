"""The error envelope: `{ "error": { "code", "message" } }` (Consistency
Conventions). This is only registered for `AppError` — FastAPI/Pydantic's
default validation error handling for malformed request bodies (422) is left
untouched, per the spec's I/O Matrix ("Standard Pydantic validation, not the
auth envelope")."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
