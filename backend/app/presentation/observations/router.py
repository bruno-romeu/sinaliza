"""`POST /pedagogical-observations`, behind `get_current_user` (spec
Boundaries & Constraints). `author_user_id` is taken from
`get_current_user`'s `sub` claim — the authenticated bearer's identity —
never a request field."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.application.observations.errors import ClassroomNotFoundError, StudentNotEnrolledError
from app.application.observations.register_observation import RegisterObservationService
from app.composition import get_register_observation_service
from app.presentation.auth.dependencies import CurrentUser, get_current_user
from app.presentation.errors import AppError
from app.presentation.schemas.observations import (
    PedagogicalObservationCreateRequest,
    PedagogicalObservationOut,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post(
    "/pedagogical-observations", response_model=PedagogicalObservationOut, status_code=201
)
def register_observation(
    payload: PedagogicalObservationCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: RegisterObservationService = Depends(get_register_observation_service),
) -> PedagogicalObservationOut:
    try:
        observation = service.execute(
            student_id=payload.student_id,
            classroom_id=payload.classroom_id,
            text=payload.text,
            author_user_id=uuid.UUID(current_user.id),
            registers_concern=payload.registers_concern,
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

    return PedagogicalObservationOut(
        id=str(observation.id),
        student_id=str(observation.student_id),
        author_user_id=str(observation.author_user_id),
        text=observation.text,
        created_at=observation.created_at,
        registers_concern=observation.registers_concern,
    )
