"""`POST /follow-ups`, `GET /follow-ups/{id}` — behind `get_current_user`,
same as every other product route (spec Boundaries & Constraints).

`responsible_user_id` is taken from `get_current_user`'s `sub` claim — the
authenticated bearer's identity — never a request field (spec Boundaries &
Constraints, mirrors `observations/router.py`'s `author_user_id` idiom).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.application.followups.change_follow_up_status import ChangeFollowUpStatusService
from app.application.followups.errors import (
    FollowUpAccessDeniedError,
    FollowUpNotFoundError,
    TrajectoryChangeMismatchError,
    TrajectoryChangeNotFoundError,
)
from app.application.followups.get_follow_up import GetFollowUpService
from app.application.followups.open_follow_up import OpenFollowUpService
from app.application.followups.register_follow_up_action import RegisterFollowUpActionService
from app.composition import (
    get_change_follow_up_status_service,
    get_get_follow_up_service,
    get_open_follow_up_service,
    get_register_follow_up_action_service,
)
from app.domain.follow_up import FollowUpStatus
from app.presentation.auth.dependencies import CurrentUser, get_current_user
from app.presentation.errors import AppError
from app.presentation.schemas.follow_ups import (
    ChangeFollowUpStatusRequest,
    FollowUpActionOut,
    FollowUpDetailOut,
    FollowUpOut,
    OpenFollowUpRequest,
    RegisterFollowUpActionRequest,
    TrajectoryChangeEvidenceGroupOut,
)
from app.presentation.schemas.trajectory import EvidenceItemOut, TrajectoryChangeOut

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
    current_user: CurrentUser = Depends(get_current_user),
    service: GetFollowUpService = Depends(get_get_follow_up_service),
) -> FollowUpDetailOut:
    try:
        result = service.execute(follow_up_id, requesting_user_id=uuid.UUID(current_user.id))
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
        actions=[
            FollowUpActionOut(
                id=action.id,
                follow_up_id=action.follow_up_id,
                description=action.description,
                author_user_id=action.author_user_id,
                created_at=action.created_at,
            )
            for action in result.actions
        ],
        trajectory_changes=[
            TrajectoryChangeEvidenceGroupOut(
                trajectory_change=TrajectoryChangeOut(
                    id=group.trajectory_change.id,
                    type=group.trajectory_change.type.value,
                    period_id=group.trajectory_change.period_id,
                    detected_at=group.trajectory_change.detected_at,
                    description=group.trajectory_change.description,
                ),
                evidence=[
                    EvidenceItemOut(
                        source_type=item.source_type.value,
                        description=item.description,
                        date=item.date,
                    )
                    for item in group.evidence
                ],
            )
            for group in result.trajectory_changes
        ],
    )


@router.post(
    "/follow-ups/{follow_up_id}/actions", response_model=FollowUpActionOut, status_code=201
)
def register_follow_up_action(
    follow_up_id: uuid.UUID,
    payload: RegisterFollowUpActionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: RegisterFollowUpActionService = Depends(get_register_follow_up_action_service),
) -> FollowUpActionOut:
    try:
        action = service.execute(
            follow_up_id=follow_up_id,
            description=payload.description,
            author_user_id=uuid.UUID(current_user.id),
        )
    except FollowUpNotFoundError as exc:
        raise AppError(
            status_code=404,
            code="follow_up_not_found",
            message="Acompanhamento não encontrado.",
        ) from exc
    except FollowUpAccessDeniedError as exc:
        raise AppError(
            status_code=403,
            code="follow_up_access_denied",
            message="Você não tem permissão para registrar uma ação neste acompanhamento.",
        ) from exc

    return FollowUpActionOut(
        id=action.id,
        follow_up_id=action.follow_up_id,
        description=action.description,
        author_user_id=action.author_user_id,
        created_at=action.created_at,
    )


@router.patch("/follow-ups/{follow_up_id}/status", response_model=FollowUpOut)
def change_follow_up_status(
    follow_up_id: uuid.UUID,
    payload: ChangeFollowUpStatusRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: ChangeFollowUpStatusService = Depends(get_change_follow_up_status_service),
) -> FollowUpOut:
    try:
        follow_up = service.execute(
            follow_up_id=follow_up_id,
            status=FollowUpStatus(payload.status),
            requesting_user_id=uuid.UUID(current_user.id),
        )
    except FollowUpNotFoundError as exc:
        raise AppError(
            status_code=404,
            code="follow_up_not_found",
            message="Acompanhamento não encontrado.",
        ) from exc
    except FollowUpAccessDeniedError as exc:
        raise AppError(
            status_code=403,
            code="follow_up_access_denied",
            message="Você não tem permissão para alterar o status deste acompanhamento.",
        ) from exc

    return FollowUpOut(
        id=follow_up.id,
        student_id=follow_up.student_id,
        status=follow_up.status.value,
        created_at=follow_up.created_at,
    )
