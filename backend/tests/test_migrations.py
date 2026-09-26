"""Regression test for the enum create/drop lifecycle documented in
`alembic/versions/0001_create_users_table.py`.

`op.drop_table("users")` does not reliably reverse the `CREATE TYPE` that
`op.create_table` issues for the table's native Postgres `user_role` enum
column, so a downgrade followed by another upgrade used to fail with
`DuplicateObject: type "user_role" already exists`. `conftest.py`'s other
fixtures build the schema via `Base.metadata.create_all()`, which never
drives Alembic's `upgrade()`/`downgrade()` functions at all and so would
never catch this — this test drives the real migration through Alembic
itself against `TEST_DATABASE_URL`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def _drop_alembic_version_table(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        connection.commit()


@pytest.fixture()
def migration_engine(engine: Engine) -> Engine:
    # Reuses the same physical test database as the other fixtures (see
    # conftest.engine), first resetting it to a clean slate so this test's
    # own upgrade/downgrade/upgrade cycle is unambiguous regardless of what
    # already ran. It leaves the schema at "head" afterwards — column-for-
    # column identical to what `Base.metadata.create_all()` produces — so
    # other tests in the session are unaffected regardless of run order.
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        connection.execute(text("DROP TABLE IF EXISTS users"))
        connection.execute(text("DROP TYPE IF EXISTS user_role"))
        connection.commit()
    yield engine
    _drop_alembic_version_table(engine)


def test_migration_upgrade_downgrade_upgrade_does_not_raise(migration_engine: Engine) -> None:
    cfg = _alembic_config()

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    # This second upgrade is exactly the step that used to raise
    # `DuplicateObject: type "user_role" already exists`.
    command.upgrade(cfg, "head")

    with migration_engine.connect() as connection:
        table_exists = connection.execute(
            text("SELECT to_regclass('public.users') IS NOT NULL")
        ).scalar_one()
    assert table_exists is True
