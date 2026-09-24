"""create users table

Revision ID: 0001
Revises:
Create Date: 2026-09-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Managed explicitly (checkfirst=True on both create and drop) rather than
# relying on SQLAlchemy's table-level before_create/after_drop auto-hooks:
# those hooks fire reliably for `op.create_table`'s CREATE TYPE, but do not
# reliably reverse it on `op.drop_table`'s DROP TABLE — so a downgrade
# followed by another upgrade previously failed with
# `DuplicateObject: type "user_role" already exists`. `create_type=False` on
# the column's own ENUM instance stops it from *also* trying to manage the
# type, avoiding a double CREATE/DROP.
user_role_enum = postgresql.ENUM("COORDENACAO_PEDAGOGICA", name="user_role")


def upgrade() -> None:
    bind = op.get_bind()
    user_role_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "COORDENACAO_PEDAGOGICA", name="user_role", create_type=False
            ),
            nullable=False,
            server_default="COORDENACAO_PEDAGOGICA",
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    user_role_enum.drop(op.get_bind(), checkfirst=True)
