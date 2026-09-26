"""create classrooms/students/enrollments/attendance_records tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Same explicit checkfirst=True / create_type=False lifecycle as
# 0001_create_users_table.py — `op.drop_table` does not reliably reverse the
# `CREATE TYPE` issued by `op.create_table`, so downgrade below drops both
# enums explicitly after their owning tables are gone.
dataset_split_enum = postgresql.ENUM("TRAIN", "EVAL_DEMO", name="dataset_split")
attendance_status_enum = postgresql.ENUM(
    "PRESENT", "ABSENT_JUSTIFIED", "ABSENT_UNJUSTIFIED", name="attendance_status"
)


def upgrade() -> None:
    bind = op.get_bind()
    dataset_split_enum.create(bind, checkfirst=True)
    attendance_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "classrooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("academic_year", sa.Integer(), nullable=False),
        sa.UniqueConstraint("name", name="uq_classroom_name"),
    )

    op.create_table(
        "students",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "dataset_split",
            postgresql.ENUM("TRAIN", "EVAL_DEMO", name="dataset_split", create_type=False),
            nullable=False,
        ),
    )

    op.create_table(
        "enrollments",
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
        sa.UniqueConstraint(
            "student_id", "classroom_id", name="uq_enrollment_student_classroom"
        ),
    )
    op.create_index("ix_enrollments_student_id", "enrollments", ["student_id"])
    op.create_index("ix_enrollments_classroom_id", "enrollments", ["classroom_id"])

    op.create_table(
        "attendance_records",
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
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PRESENT",
                "ABSENT_JUSTIFIED",
                "ABSENT_UNJUSTIFIED",
                name="attendance_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "student_id", "classroom_id", "date", name="uq_attendance_student_classroom_date"
        ),
    )
    op.create_index("ix_attendance_records_student_id", "attendance_records", ["student_id"])
    op.create_index("ix_attendance_records_classroom_id", "attendance_records", ["classroom_id"])


def downgrade() -> None:
    op.drop_index("ix_attendance_records_classroom_id", table_name="attendance_records")
    op.drop_index("ix_attendance_records_student_id", table_name="attendance_records")
    op.drop_table("attendance_records")

    op.drop_index("ix_enrollments_classroom_id", table_name="enrollments")
    op.drop_index("ix_enrollments_student_id", table_name="enrollments")
    op.drop_table("enrollments")

    op.drop_table("students")
    op.drop_table("classrooms")

    attendance_status_enum.drop(op.get_bind(), checkfirst=True)
    dataset_split_enum.drop(op.get_bind(), checkfirst=True)
