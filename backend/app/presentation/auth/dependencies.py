"""`get_current_user` — a dependência de autenticação que todo router de
produto aplica.

Nasceu na Story 1.1 sem rota nenhuma por trás — aquela story só emitia o token
em `/auth/login`, e proteger qualquer outra rota estava explicitamente fora do
escopo dela —, e esta docstring dizia exatamente isso. A frase envelheceu:
hoje a dependência está no `APIRouter` de `assignments`, `attendance`,
`follow_ups`, `grades`, `home`, `observations` e `trajectory`, e também por
rota naquelas que precisam da identidade do chamador (`CurrentUser`). Quem
impede uma rota nova de escapar disso é `tests/test_api_exposure_contract.py`:
um router registrado sem `Depends(get_current_user)` quebra lá, não em
produção (`epic-1-retro-item-6`).

Reads `sub`/`name`/`role` straight out of the validated JWT claims — no DB
round-trip (spec Design Notes, mirrors the stateless-bearer design of AD-8).
The claims are validated for *shape* here, though: every route that needs the
caller's identity does `uuid.UUID(current_user.id)`, so a correctly signed
token carrying a non-UUID (or missing) `sub` would raise `ValueError`/
`KeyError` inside the router and surface as an unhandled 500. It is answered
as the 401 any other unusable token gets.
"""

from __future__ import annotations

import uuid
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
        raise _invalid_token()

    try:
        claims = token_issuer.decode(credentials.credentials)
    except InvalidTokenError as exc:
        raise _invalid_token() from exc

    return CurrentUser(
        id=str(_require_uuid_claim(claims, "sub")),
        name=_require_str_claim(claims, "name"),
        role=_require_str_claim(claims, "role"),
    )


def _invalid_token() -> AppError:
    return AppError(
        status_code=401,
        code="invalid_token",
        message="Sessão expirada ou inválida.",
    )


def _require_str_claim(claims: dict[str, object], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value:
        raise _invalid_token()
    return value


def _require_uuid_claim(claims: dict[str, object], name: str) -> uuid.UUID:
    try:
        return uuid.UUID(_require_str_claim(claims, name))
    except ValueError as exc:
        raise _invalid_token() from exc
