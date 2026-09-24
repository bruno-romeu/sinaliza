"""Implements `PasswordHasherPort` with bcrypt — passwords are never stored
or compared in plaintext (RNF-05)."""

from __future__ import annotations

import bcrypt

_MAX_PASSWORD_BYTES = 72


class PasswordTooLongError(ValueError):
    """Raised when a plaintext password exceeds bcrypt's 72-byte input limit."""


class BcryptPasswordHasher:
    def hash(self, plain_password: str) -> str:
        encoded = plain_password.encode("utf-8")
        if len(encoded) > _MAX_PASSWORD_BYTES:
            raise PasswordTooLongError(
                f"Password is {len(encoded)} bytes, but bcrypt supports at most "
                f"{_MAX_PASSWORD_BYTES} bytes — use a shorter password."
            )
        return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")

    def verify(self, plain_password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            # Malformed/foreign hash format — never a match, never a crash.
            return False
