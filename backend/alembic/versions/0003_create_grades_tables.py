"""create academic_periods/grades tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# No new native enum needed (spec Code Map) — `Grade.value` is bounded by a
# plain CHECK constraint (`ck_grade_value_range`), not a Postgres enum.


def upgrade() -> None:
    op.create_table(
        "academic_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
    )

    op.create_table(
        "grades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id"),
            nullable=False,
        ),
        sa.Column(
            "classroom_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("classrooms.id"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column(
            "period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("academic_periods.id"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(4, 2), nullable=False),
        sa.CheckConstraint("value >= 0 AND value <= 10", name="ck_grade_value_range"),
    )
    op.create_index("ix_grades_student_id", "grades", ["student_id"])
    op.create_index("ix_grades_classroom_id", "grades", ["classroom_id"])
    op.create_index("ix_grades_period_id", "grades", ["period_id"])


def downgrade() -> None:
    op.drop_index("ix_grades_period_id", table_name="grades")
    op.drop_index("ix_grades_classroom_id", table_name="grades")
    op.drop_index("ix_grades_student_id", table_name="grades")
    op.drop_table("grades")

    op.drop_table("academic_periods")
