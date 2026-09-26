"""`GET /classrooms`, `GET /classrooms/{classroom_id}/students`, `POST
/attendance` — the first routes to actually apply `get_current_user` (spec
Boundaries & Constraints)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.application.attendance.errors import (
    ClassroomNotFoundError,
    DuplicateAttendanceError,
    StudentNotEnrolledError,
)
from app.application.attendance.list_classrooms import ListClassroomsService
from app.application.attendance.list_enrolled_students import ListEnrolledStudentsService
from app.application.attendance.register_attendance import RegisterAttendanceService
from app.composition import (
    get_list_classrooms_service,
    get_list_enrolled_students_service,
    get_register_attendance_service,
)
from app.domain.attendance import AttendanceStatus
from app.presentation.auth.dependencies import get_current_user
from app.presentation.errors import AppError
from app.presentation.schemas.attendance import (
    AttendanceCreateRequest,
    AttendanceRecordOut,
    ClassroomOut,
    StudentOut,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/classrooms", response_model=list[ClassroomOut])
def list_classrooms(
    service: ListClassroomsService = Depends(get_list_classrooms_service),
) -> list[ClassroomOut]:
    classrooms = service.execute()
    return [
        ClassroomOut(id=str(classroom.id), name=classroom.name, academic_year=classroom.academic_year)
        for classroom in classrooms
    ]


@router.get("/classrooms/{classroom_id}/students", response_model=list[StudentOut])
def list_enrolled_students(
    classroom_id: uuid.UUID,
    service: ListEnrolledStudentsService = Depends(get_list_enrolled_students_service),
) -> list[StudentOut]:
    try:
        students = service.execute(classroom_id)
    except ClassroomNotFoundError as exc:
        raise AppError(
            status_code=404,
            code="classroom_not_found",
            message="Turma não encontrada.",
        ) from exc

    return [StudentOut(id=str(student.id), name=student.name) for student in students]


@router.post("/attendance", response_model=AttendanceRecordOut, status_code=201)
def register_attendance(
    payload: AttendanceCreateRequest,
    service: RegisterAttendanceService = Depends(get_register_attendance_service),
) -> AttendanceRecordOut:
    try:
        record = service.execute(
            student_id=payload.student_id,
            classroom_id=payload.classroom_id,
            date_=payload.date,
            status=AttendanceStatus(payload.status),
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
    except DuplicateAttendanceError as exc:
        raise AppError(
            status_code=409,
            code="duplicate_attendance",
            message="Já existe registro de presença para este aluno, turma e data.",
        ) from exc

    return AttendanceRecordOut(
        id=str(record.id),
        student_id=str(record.student_id),
        classroom_id=str(record.classroom_id),
        date=record.date,
        status=record.status.value,
    )
