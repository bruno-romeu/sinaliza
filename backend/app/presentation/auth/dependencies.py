"""`get_current_user` — scaffolded in this story for Stories 1.2+ to reuse.

Not applied to any route yet: this story protects nothing besides issuing the
token at `/auth/login` (spec Boundaries & Constraints — "protecting any
backend route besides `/auth/login`" is explicitly out of scope here).

Reads `sub`/`name`/`role` straight out of the validated JWT claims — no DB
round-trip (spec Design Notes, mirrors the stateless-bearer design of AD-8).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.composition import get_token_issuer
from app.infrastructure.security.jwt_issuer import InvalidTokenError, JwtTokenIssuer
from app.presentation.errors import AppError

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    name: str
    role: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    token_issuer: JwtTokenIssuer = Depends(get_token_issuer),
) -> CurrentUser:
    if credentials is None or not credentials.credentials:
        raise AppError(
            status_code=401,
            code="invalid_token",
            message="Sessão expirada ou inválida.",
        )

    try:
        claims = token_issuer.decode(credentials.credentials)
    except InvalidTokenError as exc:
        raise AppError(
            status_code=401,
            code="invalid_token",
            message="Sessão expirada ou inválida.",
        ) from exc

    return CurrentUser(id=claims["sub"], name=claims["name"], role=claims["role"])
