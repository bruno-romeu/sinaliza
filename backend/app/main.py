from __future__ import annotations

from fastapi import FastAPI

from app.presentation.assignments.router import router as assignments_router
from app.presentation.attendance.router import router as attendance_router
from app.presentation.auth.router import router as auth_router
from app.presentation.errors import register_error_handlers
from app.presentation.grades.router import router as grades_router
from app.presentation.home.router import router as home_router
from app.presentation.observations.router import router as observations_router
from app.presentation.trajectory.router import router as trajectory_router


def create_app() -> FastAPI:
    app = FastAPI(title="Sinaliza API", version="0.1.0")
    register_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(attendance_router)
    app.include_router(grades_router)
    app.include_router(assignments_router)
    app.include_router(observations_router)
    app.include_router(trajectory_router)
    app.include_router(home_router)
    return app


app = create_app()
