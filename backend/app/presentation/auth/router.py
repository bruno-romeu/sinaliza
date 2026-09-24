from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.auth.authenticate_user import AuthenticateUserService
from app.application.auth.errors import InvalidCredentialsError
from app.composition import get_authenticate_user_service
from app.presentation.errors import AppError
from app.presentation.schemas.auth import LoginRequest, LoginResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    service: AuthenticateUserService = Depends(get_authenticate_user_service),
) -> LoginResponse:
    try:
        token, user = service.execute(payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise AppError(
            status_code=401,
            code="invalid_credentials",
            message="Login ou senha inválidos.",
        ) from exc

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut(id=str(user.id), name=user.name, email=user.email, role=user.role.value),
    )
