"""create assignments/assignment_submissions tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Same explicit checkfirst=True / create_type=False lifecycle as
# 0002_create_attendance_tables.py — `op.drop_table` does not reliably
# reverse the `CREATE TYPE` issued by `op.create_table`, so downgrade below
# drops the enum explicitly after its owning table is gone.
assignment_submission_status_enum = postgresql.ENUM(
    "DELIVERED", "NOT_DELIVERED", "PARTIAL", name="assignment_submission_status"
)


def upgrade() -> None:
    bind = op.get_bind()
    assignment_submission_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
        sa.Column("due_date", sa.Date(), nullable=False),
    )
    op.create_index("ix_assignments_classroom_id", "assignments", ["classroom_id"])
    op.create_index("ix_assignments_period_id", "assignments", ["period_id"])

    op.create_table(
        "assignment_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assignment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assignments.id"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "DELIVERED",
                "NOT_DELIVERED",
                "PARTIAL",
                name="assignment_submission_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
    )
    op.create_index(
        "ix_assignment_submissions_assignment_id", "assignment_submissions", ["assignment_id"]
    )
    op.create_index(
        "ix_assignment_submissions_student_id", "assignment_submissions", ["student_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_assignment_submissions_student_id", table_name="assignment_submissions")
    op.drop_index("ix_assignment_submissions_assignment_id", table_name="assignment_submissions")
    op.drop_table("assignment_submissions")

    op.drop_index("ix_assignments_period_id", table_name="assignments")
    op.drop_index("ix_assignments_classroom_id", table_name="assignments")
    op.drop_table("assignments")

    assignment_submission_status_enum.drop(op.get_bind(), checkfirst=True)
