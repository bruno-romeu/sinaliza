"""Ports (interfaces) the `application` layer depends on.

`application/` only ever sees these Protocols — never a concrete class from
`infrastructure/` (AD-2). Concrete adapters are wired up in `presentation/`
(the composition root) and injected here.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.user import User


class UserRepositoryPort(Protocol):
    def get_by_email(self, email: str) -> User | None: ...


class PasswordHasherPort(Protocol):
    def hash(self, plain_password: str) -> str: ...

    def verify(self, plain_password: str, password_hash: str) -> bool: ...


class TokenIssuerPort(Protocol):
    def issue(self, user: User) -> str: ...
