"""`POST /assignments`, `GET /classrooms/{classroom_id}/assignments`, `POST
/assignment-submissions` — all behind `get_current_user` (spec Boundaries &
Constraints)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.application.assignments.errors import (
    AcademicPeriodNotFoundError,
    AssignmentNotFoundError,
    ClassroomNotFoundError,
    StudentNotEnrolledError,
)
from app.application.assignments.list_assignments import ListAssignmentsByClassroomService
from app.application.assignments.register_assignment import RegisterAssignmentService
from app.application.assignments.register_submission import RegisterSubmissionService
from app.composition import (
    get_list_assignments_by_classroom_service,
    get_register_assignment_service,
    get_register_submission_service,
)
from app.domain.assignment_submission import AssignmentSubmissionStatus
from app.presentation.auth.dependencies import get_current_user
from app.presentation.errors import AppError
from app.presentation.schemas.assignments import (
    AssignmentCreateRequest,
    AssignmentOut,
    AssignmentSubmissionCreateRequest,
    AssignmentSubmissionOut,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/assignments", response_model=AssignmentOut, status_code=201)
def register_assignment(
    payload: AssignmentCreateRequest,
    service: RegisterAssignmentService = Depends(get_register_assignment_service),
) -> AssignmentOut:
    try:
        assignment = service.execute(
            classroom_id=payload.classroom_id,
            subject=payload.subject,
            period_id=payload.period_id,
            due_date=payload.due_date,
        )
    except ClassroomNotFoundError as exc:
        raise AppError(
            status_code=404,
            code="classroom_not_found",
            message="Turma não encontrada.",
        ) from exc
    except AcademicPeriodNotFoundError as exc:
        raise AppError(
            status_code=404,
            code="academic_period_not_found",
            message="Período letivo não encontrado.",
        ) from exc

    return AssignmentOut(
        id=str(assignment.id),
        classroom_id=str(assignment.classroom_id),
        subject=assignment.subject,
        period_id=str(assignment.period_id),
        due_date=assignment.due_date,
    )


@router.get("/classrooms/{classroom_id}/assignments", response_model=list[AssignmentOut])
def list_assignments_by_classroom(
    classroom_id: uuid.UUID,
    service: ListAssignmentsByClassroomService = Depends(get_list_assignments_by_classroom_service),
) -> list[AssignmentOut]:
    try:
        assignments = service.execute(classroom_id)
    except ClassroomNotFoundError as exc:
        raise AppError(
            status_code=404,
            code="classroom_not_found",
            message="Turma não encontrada.",
        ) from exc

    return [
        AssignmentOut(
            id=str(assignment.id),
            classroom_id=str(assignment.classroom_id),
            subject=assignment.subject,
            period_id=str(assignment.period_id),
            due_date=assignment.due_date,
        )
        for assignment in assignments
    ]


@router.post(
    "/assignment-submissions", response_model=AssignmentSubmissionOut, status_code=201
)
def register_assignment_submission(
    payload: AssignmentSubmissionCreateRequest,
    service: RegisterSubmissionService = Depends(get_register_submission_service),
) -> AssignmentSubmissionOut:
    try:
        submission = service.execute(
            assignment_id=payload.assignment_id,
            student_id=payload.student_id,
            status=AssignmentSubmissionStatus(payload.status),
            date_=payload.date,
        )
    except AssignmentNotFoundError as exc:
        raise AppError(
            status_code=404,
            code="assignment_not_found",
            message="Atividade não encontrada.",
        ) from exc
    except StudentNotEnrolledError as exc:
        raise AppError(
            status_code=422,
            code="student_not_enrolled",
            message="Estudante não está matriculado nesta turma.",
        ) from exc

    return AssignmentSubmissionOut(
        id=str(submission.id),
        assignment_id=str(submission.assignment_id),
        student_id=str(submission.student_id),
        status=submission.status.value,
        date=submission.date,
    )
