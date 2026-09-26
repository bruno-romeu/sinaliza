"""Composition root — the only place allowed to import concrete
`infrastructure/` classes and wire them into `application/` services or
ports. `presentation/` (routers, dependencies) imports only the factory
functions below, never `infrastructure/` itself (AD-2: "presentation...
nunca acessa infrastructure diretamente").
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.auth.authenticate_user import AuthenticateUserService
from app.config import Settings, get_settings
from app.infrastructure.db.base import get_db
from app.infrastructure.repositories.sqlalchemy_user_repository import SqlAlchemyUserRepository
from app.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher
from app.infrastructure.security.jwt_issuer import JwtTokenIssuer


def get_token_issuer(settings: Settings = Depends(get_settings)) -> JwtTokenIssuer:
    return JwtTokenIssuer(settings)


def get_authenticate_user_service(
    db: Session = Depends(get_db),
    token_issuer: JwtTokenIssuer = Depends(get_token_issuer),
) -> AuthenticateUserService:
    return AuthenticateUserService(
        user_repository=SqlAlchemyUserRepository(db),
        password_hasher=BcryptPasswordHasher(),
        token_issuer=token_issuer,
    )
