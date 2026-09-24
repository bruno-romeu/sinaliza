"""Shared fixtures for `backend/tests`.

Tests run against a real PostgreSQL test database (`TEST_DATABASE_URL`), not
sqlite — the spec requires the I/O Matrix be verified against real Postgres
(unique-index/enum behavior included). Each test runs inside its own
transaction that is rolled back afterwards, so tests never see each other's
writes and the schema only needs to be created once per session.
"""

from __future__ import annotations

import os

# Settings() is constructed at import time by app.infrastructure.db.base, so
# required env vars must exist before any `app.*` module is imported.
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://sinaliza:sinaliza@localhost:5433/sinaliza_test"
    ),
)
os.environ.setdefault("JWT_SECRET", "test-only-secret-do-not-use-in-prod")

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.engine import Connection, Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.config import Settings, get_settings  # noqa: E402
from app.domain.user import UserRole  # noqa: E402
from app.infrastructure.db.base import Base, get_db  # noqa: E402
from app.infrastructure.db.models import UserModel  # noqa: E402
from app.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher  # noqa: E402
from app.main import app  # noqa: E402

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://sinaliza:sinaliza@localhost:5433/sinaliza_test"
)


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL,
        jwt_secret="test-only-secret-do-not-use-in-prod",
        jwt_expire_minutes=60,
    )


@pytest.fixture(scope="session")
def engine(test_settings: Settings) -> Generator[Engine, None, None]:
    engine = create_engine(test_settings.database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_connection(engine: Engine) -> Generator[Connection, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    yield connection
    # A test that deliberately triggers a DB-level error (e.g. the
    # UNIQUE(email) constraint) can leave the DBAPI connection's transaction
    # already ended by the driver itself — rollback() on an
    # already-deassociated transaction is a harmless no-op, just noisy.
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture()
def db_session(db_connection: Connection) -> Generator[Session, None, None]:
    """A Session joined onto `db_connection`'s outer transaction via a
    SAVEPOINT, so route/service code can call `session.commit()` normally
    (as it does in production) while the whole test still rolls back at the
    end — see SQLAlchemy's "Joining a Session into an External Transaction"
    recipe."""
    session_factory = sessionmaker(bind=db_connection)
    session = session_factory()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, transaction) -> None:
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    yield session
    session.close()


@pytest.fixture()
def client(db_session: Session, test_settings: Settings) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_get_settings() -> Settings:
        return test_settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_user(db_session: Session) -> UserModel:
    hasher = BcryptPasswordHasher()
    user = UserModel(
        name="Coordenação Teste",
        email="coordenacao@escola.test",
        password_hash=hasher.hash("Senha-Correta-123"),
        role=UserRole.COORDENACAO_PEDAGOGICA,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
