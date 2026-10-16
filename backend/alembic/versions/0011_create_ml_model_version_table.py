"""create ml_model_version table

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-16

Persists one row per successful `python -m app.ml.train` run (spec-5-1,
RF-17). No enum columns here, unlike most prior migrations in this chain —
plain table creation, shaped like `0006_create_synthetic_generation_runs_table.py`
minus the enum lifecycle.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ml_model_version",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("artifact_path", sa.String(length=1024), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("version", name="uq_ml_model_version_version"),
    )


def downgrade() -> None:
    op.drop_table("ml_model_version")
