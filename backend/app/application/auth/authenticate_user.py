"""`AuthenticateUserService` — the one use-case this story implements.

Verifies email/password against `UserRepositoryPort` + `PasswordHasherPort`
and, on success, issues a bearer token via `TokenIssuerPort`. On any
mismatch (unknown email *or* wrong password) it raises the same
`InvalidCredentialsError`, so the presentation layer cannot accidentally leak
which one was wrong — that is enforced by construction, not by convention at
the router.
"""

from __future__ import annotations

from app.application.auth.errors import InvalidCredentialsError
from app.application.auth.ports import PasswordHasherPort, TokenIssuerPort, UserRepositoryPort
from app.domain.user import User

# A syntactically valid bcrypt hash of an unguessable placeholder, used to run
# `verify()` even when no user was found for the given email. Without this,
# an unknown-email login would return in roughly the time of a dict lookup
# while a wrong-password login pays for a full bcrypt comparison — a timing
# side-channel that would let an attacker distinguish "email doesn't exist"
# from "email exists, password wrong" even though both return an identical
# response body.
_DUMMY_PASSWORD_HASH = "$2b$12$C6UzMDM.H6dfI/f/IKcEeO2fLipsu7yeqfC9j/hpn8cLxBQaAY/xC"


class AuthenticateUserService:
    def __init__(
        self,
        user_repository: UserRepositoryPort,
        password_hasher: PasswordHasherPort,
        token_issuer: TokenIssuerPort,
    ) -> None:
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._token_issuer = token_issuer

    def execute(self, email: str, password: str) -> tuple[str, User]:
        user = self._user_repository.get_by_email(email)
        password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH

        password_matches = self._password_hasher.verify(password, password_hash)

        if user is None or not password_matches:
            raise InvalidCredentialsError()

        token = self._token_issuer.issue(user)
        return token, user
