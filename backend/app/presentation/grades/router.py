"""`GET /academic-periods`, `POST /grades` — both behind `get_current_user`
(spec Boundaries & Constraints)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.academic_periods.list_academic_periods import ListAcademicPeriodsService
from app.application.grades.errors import (
    AcademicPeriodNotFoundError,
    ClassroomNotFoundError,
    StudentNotEnrolledError,
)
from app.application.grades.register_grade import RegisterGradeService
from app.composition import get_list_academic_periods_service, get_register_grade_service
from app.presentation.auth.dependencies import get_current_user
from app.presentation.errors import AppError
from app.presentation.schemas.grades import AcademicPeriodOut, GradeCreateRequest, GradeOut

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/academic-periods", response_model=list[AcademicPeriodOut])
def list_academic_periods(
    service: ListAcademicPeriodsService = Depends(get_list_academic_periods_service),
) -> list[AcademicPeriodOut]:
    periods = service.execute()
    return [
        AcademicPeriodOut(
            id=str(period.id),
            label=period.label,
            start_date=period.start_date,
            end_date=period.end_date,
            order_index=period.order_index,
        )
        for period in periods
    ]


@router.post("/grades", response_model=GradeOut, status_code=201)
def register_grade(
    payload: GradeCreateRequest,
    service: RegisterGradeService = Depends(get_register_grade_service),
) -> GradeOut:
    try:
        grade = service.execute(
            student_id=payload.student_id,
            classroom_id=payload.classroom_id,
            subject=payload.subject,
            period_id=payload.period_id,
            date_=payload.date,
            value=payload.value,
        )
    except ClassroomNotFoundError as exc:
        raise AppError(
            status_code=404,
            code="classroom_not_found",
            message="Turma não encontrada.",
        ) from exc
    except StudentNotEnrolledError as exc:
        raise AppError(
            status_code=422,
            code="student_not_enrolled",
            message="Estudante não está matriculado nesta turma.",
        ) from exc
    except AcademicPeriodNotFoundError as exc:
        raise AppError(
            status_code=404,
            code="academic_period_not_found",
            message="Período letivo não encontrado.",
        ) from exc

    return GradeOut(
        id=str(grade.id),
        student_id=str(grade.student_id),
        classroom_id=str(grade.classroom_id),
        subject=grade.subject,
        period_id=str(grade.period_id),
        date=grade.date,
        value=grade.value,
    )
