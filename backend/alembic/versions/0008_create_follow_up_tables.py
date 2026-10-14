"""create follow_ups/follow_up_evidence tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Same explicit checkfirst=True / create_type=False enum lifecycle as
# 0007_create_trajectory_change_tables.py.
follow_up_status_enum = postgresql.ENUM(
    "EM_OBSERVACAO",
    "ACOMPANHAMENTO_ATIVO",
    "AGUARDANDO_RETORNO",
    "ENCERRADO",
    name="follow_up_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    follow_up_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "follow_ups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "EM_OBSERVACAO",
                "ACOMPANHAMENTO_ATIVO",
                "AGUARDANDO_RETORNO",
                "ENCERRADO",
                name="follow_up_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "responsible_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("next_review_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_follow_ups_student_id", "follow_ups", ["student_id"])
    op.create_index(
        "ix_follow_ups_responsible_user_id", "follow_ups", ["responsible_user_id"]
    )

    op.create_table(
        "follow_up_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "follow_up_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("follow_ups.id"),
            nullable=False,
        ),
        sa.Column(
            "trajectory_change_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trajectory_changes.id"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_follow_up_evidence_follow_up_id", "follow_up_evidence", ["follow_up_id"]
    )
    op.create_index(
        "ix_follow_up_evidence_trajectory_change_id",
        "follow_up_evidence",
        ["trajectory_change_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_follow_up_evidence_trajectory_change_id", table_name="follow_up_evidence"
    )
    op.drop_index(
        "ix_follow_up_evidence_follow_up_id", table_name="follow_up_evidence"
    )
    op.drop_table("follow_up_evidence")

    op.drop_index("ix_follow_ups_responsible_user_id", table_name="follow_ups")
    op.drop_index("ix_follow_ups_student_id", table_name="follow_ups")
    op.drop_table("follow_ups")

    follow_up_status_enum.drop(op.get_bind(), checkfirst=True)
