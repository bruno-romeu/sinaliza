"""create trajectory_changes/trajectory_change_sources tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Same explicit checkfirst=True / create_type=False lifecycle as
# 0002_create_attendance_tables.py / 0004_create_assignments_tables.py —
# `op.drop_table` does not reliably reverse the `CREATE TYPE` issued by
# `op.create_table`, so downgrade below drops both enums explicitly after
# their owning tables are gone.
trajectory_change_type_enum = postgresql.ENUM(
    "ATTENDANCE_DROP",
    "GRADE_DROP",
    "MISSING_ASSIGNMENTS_INCREASE",
    "COMBINED_DETERIORATION",
    name="trajectory_change_type",
)
trajectory_change_source_type_enum = postgresql.ENUM(
    "ATTENDANCE_RECORD",
    "GRADE",
    "ASSIGNMENT_SUBMISSION",
    "PEDAGOGICAL_OBSERVATION",
    name="trajectory_change_source_type",
)


def upgrade() -> None:
    bind = op.get_bind()
    trajectory_change_type_enum.create(bind, checkfirst=True)
    trajectory_change_source_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "trajectory_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id"),
            nullable=False,
        ),
        sa.Column(
            "type",
            postgresql.ENUM(
                "ATTENDANCE_DROP",
                "GRADE_DROP",
                "MISSING_ASSIGNMENTS_INCREASE",
                "COMBINED_DETERIORATION",
                name="trajectory_change_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("academic_periods.id"),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "student_id", "type", "period_id", name="uq_trajectory_change_student_type_period"
        ),
    )
    op.create_index("ix_trajectory_changes_student_id", "trajectory_changes", ["student_id"])
    op.create_index("ix_trajectory_changes_period_id", "trajectory_changes", ["period_id"])

    op.create_table(
        "trajectory_change_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "trajectory_change_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trajectory_changes.id"),
            nullable=False,
        ),
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "ATTENDANCE_RECORD",
                "GRADE",
                "ASSIGNMENT_SUBMISSION",
                "PEDAGOGICAL_OBSERVATION",
                name="trajectory_change_source_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_index(
        "ix_trajectory_change_sources_trajectory_change_id",
        "trajectory_change_sources",
        ["trajectory_change_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_trajectory_change_sources_trajectory_change_id",
        table_name="trajectory_change_sources",
    )
    op.drop_table("trajectory_change_sources")

    op.drop_index("ix_trajectory_changes_period_id", table_name="trajectory_changes")
    op.drop_index("ix_trajectory_changes_student_id", table_name="trajectory_changes")
    op.drop_table("trajectory_changes")

    trajectory_change_source_type_enum.drop(op.get_bind(), checkfirst=True)
    trajectory_change_type_enum.drop(op.get_bind(), checkfirst=True)
