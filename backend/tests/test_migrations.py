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
    # Drop order respects FKs: assignment_submissions/assignments/grades/
    # attendance_records/pedagogical_observations/enrollments (children)
    # before students/classrooms/academic_periods/users (parents), then
    # native enum types.
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        connection.execute(text("DROP TABLE IF EXISTS synthetic_generation_runs"))
        connection.execute(text("DROP TABLE IF EXISTS assignment_submissions"))
        connection.execute(text("DROP TABLE IF EXISTS assignments"))
        connection.execute(text("DROP TABLE IF EXISTS grades"))
        connection.execute(text("DROP TABLE IF EXISTS pedagogical_observations"))
        connection.execute(text("DROP TABLE IF EXISTS attendance_records"))
        connection.execute(text("DROP TABLE IF EXISTS enrollments"))
        connection.execute(text("DROP TABLE IF EXISTS academic_periods"))
        connection.execute(text("DROP TABLE IF EXISTS students"))
        connection.execute(text("DROP TABLE IF EXISTS classrooms"))
        connection.execute(text("DROP TABLE IF EXISTS users"))
        connection.execute(text("DROP TYPE IF EXISTS synthetic_profile"))
        connection.execute(text("DROP TYPE IF EXISTS assignment_submission_status"))
        connection.execute(text("DROP TYPE IF EXISTS attendance_status"))
        connection.execute(text("DROP TYPE IF EXISTS dataset_split"))
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
        users_exists = connection.execute(
            text("SELECT to_regclass('public.users') IS NOT NULL")
        ).scalar_one()
        attendance_exists = connection.execute(
            text("SELECT to_regclass('public.attendance_records') IS NOT NULL")
        ).scalar_one()
        academic_periods_exists = connection.execute(
            text("SELECT to_regclass('public.academic_periods') IS NOT NULL")
        ).scalar_one()
        grades_exists = connection.execute(
            text("SELECT to_regclass('public.grades') IS NOT NULL")
        ).scalar_one()
        assignments_exists = connection.execute(
            text("SELECT to_regclass('public.assignments') IS NOT NULL")
        ).scalar_one()
        assignment_submissions_exists = connection.execute(
            text("SELECT to_regclass('public.assignment_submissions') IS NOT NULL")
        ).scalar_one()
        pedagogical_observations_exists = connection.execute(
            text("SELECT to_regclass('public.pedagogical_observations') IS NOT NULL")
        ).scalar_one()
        synthetic_generation_runs_exists = connection.execute(
            text("SELECT to_regclass('public.synthetic_generation_runs') IS NOT NULL")
        ).scalar_one()
        synthetic_profile_type_exists = connection.execute(
            text("SELECT to_regtype('synthetic_profile') IS NOT NULL")
        ).scalar_one()
        synthetic_profile_column_exists = connection.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'students' AND column_name = 'synthetic_profile')"
            )
        ).scalar_one()
    assert users_exists is True
    assert attendance_exists is True
    assert academic_periods_exists is True
    assert grades_exists is True
    assert assignments_exists is True
    assert assignment_submissions_exists is True
    assert pedagogical_observations_exists is True
    assert synthetic_generation_runs_exists is True
    assert synthetic_profile_type_exists is True
    assert synthetic_profile_column_exists is True

    # `test_grades.py`'s DB-bypass test only proves `ck_grade_value_range`
    # exists on the schema built by `Base.metadata.create_all()` (conftest's
    # default). Confirm it also exists on the schema this migration itself
    # built, not just the ORM model definition.
    with migration_engine.connect() as connection:
        constraint_def = connection.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_grade_value_range' AND conrelid = 'grades'::regclass"
            )
        ).scalar_one_or_none()
    assert constraint_def == "CHECK (((value >= (0)::numeric) AND (value <= (10)::numeric)))"
