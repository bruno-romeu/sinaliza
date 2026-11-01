"""Shared fixtures for `backend/tests`.

Tests run against a real PostgreSQL test database (`TEST_DATABASE_URL`), not
sqlite — the spec requires the I/O Matrix be verified against real Postgres
(unique-index/enum behavior included). Each test runs inside its own
transaction that is rolled back afterwards, so tests never see each other's
writes and the schema only needs to be created once per session.
"""

from __future__ import annotations

import os
from pathlib import Path

# Variaveis que a suite aceita herdar de `backend/.env`. E uma lista explicita,
# nao o arquivo inteiro, por um motivo concreto: o `.env` define DATABASE_URL
# apontando para o banco de DESENVOLVIMENTO, e carrega-lo aqui faria os testes
# escreverem nele. DATABASE_URL continua sendo derivado de TEST_DATABASE_URL
# logo abaixo, como sempre foi. JWT_SECRET tambem fica de fora: a suite usa o
# seu proprio segredo de teste, nunca o de dev.
_ENV_FILE_KEYS = (
    "TEST_DATABASE_URL",
    "DEV_SEED_EMAIL",
    "DEV_SEED_NAME",
    "DEV_SEED_PASSWORD",
)


def _load_env_file() -> None:
    """Preenche `os.environ` a partir de `backend/.env`, sem sobrescrever nada.

    Antes disto, `TEST_DATABASE_URL` so era lido do ambiente do processo, com um
    default fixo na porta 5433 — entao um `.env` apontando para outra porta era
    silenciosamente ignorado e a suite rodava contra o banco errado. Isso mordeu
    de verdade: dois worktrees paralelos, cada um com o seu `.env`, acabaram no
    mesmo banco e produziram `deadlock detected` que parecia defeito de codigo.

    `setdefault` garante a precedencia correta: variavel ja exportada no
    ambiente (como o CI faz) vence o arquivo, que vence o default do modulo.
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in _ENV_FILE_KEYS:
            os.environ.setdefault(key, value.strip())


_load_env_file()

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
from datetime import date  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy import text as sa_text  # noqa: E402
from sqlalchemy.engine import Connection, Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.config import Settings, get_settings  # noqa: E402
from app.domain.student import DatasetSplit  # noqa: E402
from app.domain.user import UserRole  # noqa: E402
from app.infrastructure.db.base import Base, get_db  # noqa: E402
from app.infrastructure.db.models import (  # noqa: E402
    AcademicPeriodModel,
    AssignmentModel,
    ClassroomModel,
    EnrollmentModel,
    StudentModel,
    UserModel,
)
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
    # Tests build schema from SQLAlchemy metadata, bypassing Alembic
    # entirely (this file's own docstring) — the GRANT/REVOKE applied by
    # `0009_create_follow_up_action_table.py` in production must be mirrored
    # here, identical SQL, so the privilege assertion stays verifiable under
    # the test DB too (spec Boundaries & Constraints, AD-6).
    with engine.begin() as connection:
        connection.execute(sa_text("GRANT INSERT, SELECT ON follow_up_action TO CURRENT_USER"))
        connection.execute(sa_text("REVOKE UPDATE, DELETE ON follow_up_action FROM CURRENT_USER"))
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
    recipe (2.0-style: track the SAVEPOINT on the `Connection`, not on the
    `Session`). Restarting the SAVEPOINT via `session.begin_nested()`
    instead (checking `transaction.nested`/`transaction._parent.nested`) only
    survives a single commit-then-fail cycle — a second successful
    `session.commit()` after the first SAVEPOINT restart silently stops being
    scoped to any SAVEPOINT at all, so a later failed `commit()` +
    `rollback()` (Story 1.2's duplicate-attendance path) rolls back the
    *entire* outer transaction, wiping out everything committed earlier in
    the same test, not just the failed statement."""
    session_factory = sessionmaker(bind=db_connection)
    session = session_factory()

    nested = db_connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, transaction) -> None:
        nonlocal nested
        if not nested.is_active:
            nested = db_connection.begin_nested()

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


@pytest.fixture()
def seeded_classroom(db_session: Session) -> ClassroomModel:
    classroom = ClassroomModel(name="Turma Teste", academic_year=2026)
    db_session.add(classroom)
    db_session.commit()
    db_session.refresh(classroom)
    return classroom


@pytest.fixture()
def seeded_enrolled_student(db_session: Session, seeded_classroom: ClassroomModel) -> StudentModel:
    """A student enrolled in `seeded_classroom`, `EVAL_DEMO` split."""
    student = StudentModel(name="Estudante Teste", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add(student)
    db_session.flush()
    db_session.add(EnrollmentModel(student_id=student.id, classroom_id=seeded_classroom.id))
    db_session.commit()
    db_session.refresh(student)
    return student


@pytest.fixture()
def seeded_academic_period(db_session: Session) -> AcademicPeriodModel:
    """Shaped like `seeded_classroom` (spec Code Map). Its window contains
    2026-09-24 so it can stand in for "período letivo vigente"."""
    period = AcademicPeriodModel(
        label="3º Bimestre Teste",
        start_date=date(2026, 7, 27),
        end_date=date(2026, 9, 25),
        order_index=3,
    )
    db_session.add(period)
    db_session.commit()
    db_session.refresh(period)
    return period


@pytest.fixture()
def seeded_assignment(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period: AcademicPeriodModel,
) -> AssignmentModel:
    """Shaped like `seeded_academic_period` (spec Code Map). Built on
    `seeded_classroom` + `seeded_academic_period` so submission tests have an
    atividade already cadastrada against the same turma/período."""
    assignment = AssignmentModel(
        classroom_id=seeded_classroom.id,
        subject="Matemática",
        period_id=seeded_academic_period.id,
        due_date=date(2026, 9, 30),
    )
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(assignment)
    return assignment
