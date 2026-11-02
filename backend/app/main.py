from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.presentation.assignments.router import router as assignments_router
from app.presentation.attendance.router import router as attendance_router
from app.presentation.auth.router import router as auth_router
from app.presentation.errors import register_error_handlers
from app.presentation.follow_ups.router import router as follow_ups_router
from app.presentation.grades.router import router as grades_router
from app.presentation.home.router import router as home_router
from app.presentation.observations.router import router as observations_router
from app.presentation.rate_limit import install_login_rate_limit
from app.presentation.trajectory.router import router as trajectory_router


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # As janelas do limitador de login vivem na memória deste processo
    # (app.presentation.rate_limit) e valem apenas enquanto ele vive — então
    # começam vazias a cada start. Zerar aqui torna isso explícito em vez de
    # implícito na construção do objeto.
    app.state.login_rate_limit_counter.reset()
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    # `settings` injetável para que os testes construam um app com limites
    # próprios, sem depender de variáveis de ambiente do processo.
    settings = settings or get_settings()

    app = FastAPI(title="Sinaliza API", version="0.1.0", lifespan=_lifespan)
    register_error_handlers(app)
    install_login_rate_limit(app, settings)
    app.include_router(auth_router)
    app.include_router(attendance_router)
    app.include_router(grades_router)
    app.include_router(assignments_router)
    app.include_router(observations_router)
    app.include_router(trajectory_router)
    app.include_router(home_router)
    app.include_router(follow_ups_router)
    return app


app = create_app()
