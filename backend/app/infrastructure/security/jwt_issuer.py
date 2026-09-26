"""Implements `TokenIssuerPort` with a stateless HS256 JWT bearer token — no
server-side session (AD-8, Consistency Conventions).

Claims embed `sub`/`name`/`role`/`exp` so `get_current_user` (Stories 1.2+)
never needs a DB round-trip to answer "who is this and what's their name" —
see the spec's Design Notes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config import Settings
from app.domain.user import User


class InvalidTokenError(Exception):
    """Raised when a bearer token is missing, malformed, expired, or has an
    invalid signature — never distinguished further to the caller."""


class JwtTokenIssuer:
    algorithm = "HS256"
    _required_claims = ("sub", "name", "role")

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def issue(self, user: User) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "name": user.name,
            "role": user.role.value,
            "iat": now,
            "exp": now + timedelta(minutes=self._settings.jwt_expire_minutes),
        }
        return jwt.encode(payload, self._settings.jwt_secret, algorithm=self.algorithm)

    def decode(self, token: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(token, self._settings.jwt_secret, algorithms=[self.algorithm])
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(str(exc)) from exc

        if any(claim not in claims for claim in self._required_claims):
            raise InvalidTokenError("token is missing required claims")

        return claims
