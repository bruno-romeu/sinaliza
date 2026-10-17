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

from app.domain.follow_up import FollowUpStatus
from app.domain.student import SyntheticProfile
from app.domain.trajectory_change import SourceType, TrajectoryChangeType

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
    # native enum types. `follow_up_evidence` depends on both `follow_ups`
    # and `trajectory_changes`, so it must drop before either.
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        connection.execute(text("DROP TABLE IF EXISTS follow_up_action"))
        connection.execute(text("DROP TABLE IF EXISTS follow_up_evidence"))
        connection.execute(text("DROP TABLE IF EXISTS follow_ups"))
        connection.execute(text("DROP TABLE IF EXISTS trajectory_change_sources"))
        connection.execute(text("DROP TABLE IF EXISTS trajectory_changes"))
        connection.execute(text("DROP TABLE IF EXISTS ml_prediction"))
        connection.execute(text("DROP TABLE IF EXISTS ml_model_version"))
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
        connection.execute(text("DROP TYPE IF EXISTS follow_up_status"))
        connection.execute(text("DROP TYPE IF EXISTS trajectory_change_source_type"))
        connection.execute(text("DROP TYPE IF EXISTS trajectory_change_type"))
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

    # spec-5-1: `ml_model_version` must be cleanly dropped by `downgrade()`.
    with migration_engine.connect() as connection:
        ml_model_version_dropped = connection.execute(
            text("SELECT to_regclass('public.ml_model_version') IS NULL")
        ).scalar_one()
    assert ml_model_version_dropped is True

    # spec-5-2: `ml_prediction` must be cleanly dropped by `downgrade()`.
    with migration_engine.connect() as connection:
        ml_prediction_dropped = connection.execute(
            text("SELECT to_regclass('public.ml_prediction') IS NULL")
        ).scalar_one()
    assert ml_prediction_dropped is True

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
        ml_model_version_exists = connection.execute(
            text("SELECT to_regclass('public.ml_model_version') IS NOT NULL")
        ).scalar_one()
        ml_prediction_exists = connection.execute(
            text("SELECT to_regclass('public.ml_prediction') IS NOT NULL")
        ).scalar_one()
        trajectory_changes_exists = connection.execute(
            text("SELECT to_regclass('public.trajectory_changes') IS NOT NULL")
        ).scalar_one()
        trajectory_change_sources_exists = connection.execute(
            text("SELECT to_regclass('public.trajectory_change_sources') IS NOT NULL")
        ).scalar_one()
        follow_ups_exists = connection.execute(
            text("SELECT to_regclass('public.follow_ups') IS NOT NULL")
        ).scalar_one()
        follow_up_evidence_exists = connection.execute(
            text("SELECT to_regclass('public.follow_up_evidence') IS NOT NULL")
        ).scalar_one()
        follow_up_action_exists = connection.execute(
            text("SELECT to_regclass('public.follow_up_action') IS NOT NULL")
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
    assert ml_model_version_exists is True
    assert ml_prediction_exists is True
    assert trajectory_changes_exists is True
    assert trajectory_change_sources_exists is True
    assert follow_ups_exists is True
    assert follow_up_evidence_exists is True
    assert follow_up_action_exists is True
    assert synthetic_profile_type_exists is True
    assert synthetic_profile_column_exists is True

    # The migration hardcodes the enum's member labels independently of
    # `SyntheticProfile` — asserting the type/column exist isn't enough to
    # catch the two definitions drifting apart (as happened when
    # `FALLING_GRADES` was added to the domain enum but not to 0006's
    # `ENUM(...)` literal list). Compare the actual Postgres labels.
    with migration_engine.connect() as connection:
        synthetic_profile_labels = set(
            connection.execute(
                text(
                    "SELECT e.enumlabel FROM pg_enum e "
                    "JOIN pg_type t ON e.enumtypid = t.oid "
                    "WHERE t.typname = 'synthetic_profile'"
                )
            ).scalars()
        )
    assert synthetic_profile_labels == {member.value for member in SyntheticProfile}

    # Same label-drift regression as above, for the two native enums Story
    # 3.2 added: the migration hardcodes `trajectory_change_type`'s and
    # `trajectory_change_source_type`'s member labels independently of
    # `TrajectoryChangeType`/`SourceType`, so a domain enum member added
    # without updating the migration's literal list would otherwise go
    # uncaught.
    with migration_engine.connect() as connection:
        trajectory_change_type_labels = set(
            connection.execute(
                text(
                    "SELECT e.enumlabel FROM pg_enum e "
                    "JOIN pg_type t ON e.enumtypid = t.oid "
                    "WHERE t.typname = 'trajectory_change_type'"
                )
            ).scalars()
        )
        trajectory_change_source_type_labels = set(
            connection.execute(
                text(
                    "SELECT e.enumlabel FROM pg_enum e "
                    "JOIN pg_type t ON e.enumtypid = t.oid "
                    "WHERE t.typname = 'trajectory_change_source_type'"
                )
            ).scalars()
        )
    assert trajectory_change_type_labels == {
        member.value for member in TrajectoryChangeType
    }
    assert trajectory_change_source_type_labels == {member.value for member in SourceType}

    # Same label-drift regression as above, for Story 4.1's `follow_up_status`.
    with migration_engine.connect() as connection:
        follow_up_status_labels = set(
            connection.execute(
                text(
                    "SELECT e.enumlabel FROM pg_enum e "
                    "JOIN pg_type t ON e.enumtypid = t.oid "
                    "WHERE t.typname = 'follow_up_status'"
                )
            ).scalars()
        )
    assert follow_up_status_labels == {member.value for member in FollowUpStatus}

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
