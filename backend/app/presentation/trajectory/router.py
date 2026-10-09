"""`GET /students/{student_id}/trajectory` — behind `get_current_user`, same
as every other product route (spec Boundaries & Constraints).

`window_days` is an optional query override (spec Boundaries &
Constraints: "override `?window_days=`"); when omitted, the configured
`Settings.trajectory_window_days` default applies. `gt=0, le=3650` mirrors the same
constraint `Settings.trajectory_window_days` enforces, so a non-positive or
excessively large override fails FastAPI's standard 422 validation before
ever reaching the service (an unbounded value would otherwise overflow
`date - timedelta(...)` inside the service with a raw 500)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.application.trajectory.errors import StudentNotFoundError
from app.application.trajectory.get_student_trajectory import GetStudentTrajectoryService
from app.composition import get_get_student_trajectory_service
from app.config import Settings, get_settings
from app.presentation.auth.dependencies import get_current_user
from app.presentation.errors import AppError
from app.presentation.schemas.trajectory import ConcerningFactorOut, TrajectoryChangeOut, TrajectoryOut

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/students/{student_id}/trajectory", response_model=TrajectoryOut)
def get_student_trajectory(
    student_id: uuid.UUID,
    window_days: int | None = Query(default=None, gt=0, le=3650),
    service: GetStudentTrajectoryService = Depends(get_get_student_trajectory_service),
    settings: Settings = Depends(get_settings),
) -> TrajectoryOut:
    effective_window_days = (
        window_days if window_days is not None else settings.trajectory_window_days
    )

    try:
        result = service.execute(student_id, effective_window_days)
    except StudentNotFoundError as exc:
        raise AppError(
            status_code=404,
            code="student_not_found",
            message="Estudante não encontrado.",
        ) from exc

    indicators = result.indicators
    trajectory_change_out = (
        TrajectoryChangeOut(
            type=result.trajectory_change.type.value,
            period_id=result.trajectory_change.period_id,
            detected_at=result.trajectory_change.detected_at,
            description=result.trajectory_change.description,
        )
        if result.trajectory_change is not None
        else None
    )
    concerning_factor_out = (
        ConcerningFactorOut(
            kind=result.concerning_factor.kind.value,
            description=result.concerning_factor.description,
        )
        if result.concerning_factor is not None
        else None
    )

    return TrajectoryOut(
        attendance_rate=indicators.attendance_rate,
        attendance_trend=indicators.attendance_trend,
        grade_average=indicators.grade_average,
        grade_trend=indicators.grade_trend,
        missing_assignments_count=indicators.missing_assignments_count,
        missing_assignment_delta=indicators.missing_assignment_delta,
        trajectory_change=trajectory_change_out,
        concerning_factor=concerning_factor_out,
    )
