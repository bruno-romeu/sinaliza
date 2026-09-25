"""create pedagogical_observations table

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# No new native enum needed (spec Code Map) — `text` is a plain `Text`
# column, `created_at` a plain `timestamptz`.


def upgrade() -> None:
    op.create_table(
        "pedagogical_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_pedagogical_observations_student_id", "pedagogical_observations", ["student_id"]
    )
    op.create_index(
        "ix_pedagogical_observations_author_user_id",
        "pedagogical_observations",
        ["author_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pedagogical_observations_author_user_id", table_name="pedagogical_observations"
    )
    op.drop_index(
        "ix_pedagogical_observations_student_id", table_name="pedagogical_observations"
    )
    op.drop_table("pedagogical_observations")
