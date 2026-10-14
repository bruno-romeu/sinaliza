"""create follow_up_action table

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "follow_up_action",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "follow_up_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("follow_ups.id"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "author_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_follow_up_action_follow_up_id", "follow_up_action", ["follow_up_id"])
    op.create_index(
        "ix_follow_up_action_author_user_id", "follow_up_action", ["author_user_id"]
    )

    # History append-only-ness doesn't rely only on application code (spec
    # Boundaries & Constraints, AD-6): the app's Postgres role may INSERT and
    # SELECT, never UPDATE/DELETE. `CURRENT_USER` resolves to whatever role
    # runs this migration, which is the same role the app connects as
    # (`settings.database_url`) — no hardcoded role name needed.
    op.execute("GRANT INSERT, SELECT ON follow_up_action TO CURRENT_USER")
    op.execute("REVOKE UPDATE, DELETE ON follow_up_action FROM CURRENT_USER")


def downgrade() -> None:
    op.drop_index("ix_follow_up_action_author_user_id", table_name="follow_up_action")
    op.drop_index("ix_follow_up_action_follow_up_id", table_name="follow_up_action")
    op.drop_table("follow_up_action")
