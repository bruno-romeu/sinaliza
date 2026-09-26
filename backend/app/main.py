from __future__ import annotations

from fastapi import FastAPI

from app.presentation.attendance.router import router as attendance_router
from app.presentation.auth.router import router as auth_router
from app.presentation.errors import register_error_handlers
from app.presentation.grades.router import router as grades_router


def create_app() -> FastAPI:
    app = FastAPI(title="Sinaliza API", version="0.1.0")
    register_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(attendance_router)
    app.include_router(grades_router)
    return app


app = create_app()
