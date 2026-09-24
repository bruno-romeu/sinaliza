"""Implements `UserRepositoryPort` on top of SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.user import User
from app.infrastructure.db.models import UserModel


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_email(self, email: str) -> User | None:
        # Normalized the same way as at write time (seed_dev_user.py) so
        # casing/whitespace differences never turn a real match into a
        # false "invalid credentials".
        stmt = select(UserModel).where(UserModel.email == email.strip().lower())
        model = self._session.execute(stmt).scalar_one_or_none()
        if model is None:
            return None
        return User(
            id=model.id,
            name=model.name,
            email=model.email,
            password_hash=model.password_hash,
            role=model.role,
        )
