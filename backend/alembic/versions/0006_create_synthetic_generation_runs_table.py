"""create synthetic_generation_runs table + students.synthetic_profile

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Same explicit checkfirst=True / create_type=False lifecycle as
# 0002_create_attendance_tables.py — neither `op.drop_column` nor
# `op.drop_table` reliably reverses a `CREATE TYPE`, so `downgrade` drops the
# enum explicitly after the column that uses it is gone.
synthetic_profile_enum = postgresql.ENUM(
    "STABLE",
    "FALLING_ATTENDANCE",
    "FALLING_GRADES",
    "COMBINED_DETERIORATION",
    name="synthetic_profile",
)


def upgrade() -> None:
    bind = op.get_bind()
    synthetic_profile_enum.create(bind, checkfirst=True)

    # Nullable with no backfill: students seeded by `seed_dev_fixtures.py`
    # legitimately have no profile, and Story 2.1's generator ships the
    # column NULL for every student it creates (Story 2.2 populates it).
    op.add_column(
        "students",
        sa.Column(
            "synthetic_profile",
            postgresql.ENUM(
                "STABLE",
                "FALLING_ATTENDANCE",
                "FALLING_GRADES",
                "COMBINED_DETERIORATION",
                name="synthetic_profile",
                create_type=False,
            ),
            nullable=True,
        ),
    )

    op.create_table(
        "synthetic_generation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("generator_version", sa.String(length=50), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("student_count", sa.Integer(), nullable=False),
        sa.Column("train_ratio", sa.Numeric(4, 3), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("synthetic_generation_runs")
    op.drop_column("students", "synthetic_profile")
    synthetic_profile_enum.drop(op.get_bind(), checkfirst=True)
