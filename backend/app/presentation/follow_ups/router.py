"""`POST /follow-ups`, `GET /follow-ups/{id}` — behind `get_current_user`,
same as every other product route (spec Boundaries & Constraints).

`responsible_user_id` is taken from `get_current_user`'s `sub` claim — the
authenticated bearer's identity — never a request field (spec Boundaries &
Constraints, mirrors `observations/router.py`'s `author_user_id` idiom).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.application.followups.errors import (
    FollowUpNotFoundError,
    TrajectoryChangeMismatchError,
    TrajectoryChangeNotFoundError,
)
from app.application.followups.get_follow_up import GetFollowUpService
from app.application.followups.open_follow_up import OpenFollowUpService
from app.composition import get_get_follow_up_service, get_open_follow_up_service
from app.presentation.auth.dependencies import CurrentUser, get_current_user
from app.presentation.errors import AppError
from app.presentation.schemas.follow_ups import FollowUpDetailOut, FollowUpOut, OpenFollowUpRequest
from app.presentation.schemas.trajectory import EvidenceItemOut

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/follow-ups", response_model=FollowUpOut, status_code=201)
def open_follow_up(
    payload: OpenFollowUpRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: OpenFollowUpService = Depends(get_open_follow_up_service),
) -> FollowUpOut:
    try:
        follow_up = service.execute(
            student_id=payload.student_id,
            trajectory_change_id=payload.trajectory_change_id,
            responsible_user_id=uuid.UUID(current_user.id),
        )
    except TrajectoryChangeNotFoundError as exc:
        raise AppError(
            status_code=404,
            code="trajectory_change_not_found",
            message="Mudança de trajetória não encontrada.",
        ) from exc
    except TrajectoryChangeMismatchError as exc:
        raise AppError(
            status_code=422,
            code="trajectory_change_mismatch",
            message="A mudança de trajetória não pertence a este estudante.",
        ) from exc

    return FollowUpOut(
        id=follow_up.id,
        student_id=follow_up.student_id,
        status=follow_up.status.value,
        created_at=follow_up.created_at,
    )


@router.get("/follow-ups/{follow_up_id}", response_model=FollowUpDetailOut)
def get_follow_up(
    follow_up_id: uuid.UUID,
    service: GetFollowUpService = Depends(get_get_follow_up_service),
) -> FollowUpDetailOut:
    try:
        result = service.execute(follow_up_id)
    except FollowUpNotFoundError as exc:
        raise AppError(
            status_code=404,
            code="follow_up_not_found",
            message="Acompanhamento não encontrado.",
        ) from exc

    return FollowUpDetailOut(
        id=result.follow_up.id,
        student_id=result.follow_up.student_id,
        student_name=result.student_name,
        status=result.follow_up.status.value,
        created_at=result.follow_up.created_at,
        evidence=[
            EvidenceItemOut(
                source_type=item.source_type.value,
                description=item.description,
                date=item.date,
            )
            for item in result.evidence
        ],
    )
