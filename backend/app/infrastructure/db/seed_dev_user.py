"""Idempotent dev-only CLI seeding exactly one `COORDENACAO_PEDAGOGICA` user.

Usage:
    python -m app.infrastructure.db.seed_dev_user

Reads `DEV_SEED_NAME` / `DEV_SEED_EMAIL` / `DEV_SEED_PASSWORD` from the
environment (or `.env`). There is no self-service registration screen — this
script is the only way a user ever gets created (spec Boundaries & Constraints).
Re-running with the same email is a no-op.
"""

from __future__ import annotations

import sys

from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.domain.user import UserRole
from app.infrastructure.db.base import SessionLocal
from app.infrastructure.db.models import UserModel
from app.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher


def seed_dev_user() -> None:
    settings = get_settings()

    if not settings.dev_seed_email or not settings.dev_seed_password:
        print(
            "DEV_SEED_EMAIL and DEV_SEED_PASSWORD must be set to seed a dev user; skipping.",
            file=sys.stderr,
        )
        return

    # Normalized the same way as at lookup time
    # (sqlalchemy_user_repository.py) so stored and looked-up emails always
    # compare consistently.
    email = settings.dev_seed_email.strip().lower()
    hasher = BcryptPasswordHasher()

    with SessionLocal() as session:
        existing = session.query(UserModel).filter(UserModel.email == email).one_or_none()
        if existing is not None:
            print(f"User '{email}' already exists — no-op.")
            return

        user = UserModel(
            name=settings.dev_seed_name,
            email=email,
            password_hash=hasher.hash(settings.dev_seed_password),
            role=UserRole.COORDENACAO_PEDAGOGICA,
        )
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            # Lost a race with a concurrent run that inserted the same email
            # between our existence check and this commit — same outcome as
            # the "already exists" no-op path above, not a crash.
            session.rollback()
            print(f"User '{email}' already exists — no-op.")
            return
        print(f"Seeded user '{email}'.")


if __name__ == "__main__":
    seed_dev_user()
