"""create ml_prediction table

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-16

Persists one row per `EVAL_DEMO` student scored by a
`python -m app.ml.predict` run (spec-5-2). Plain table creation, mirroring
`0011_create_ml_model_version_table.py`'s shape — no enum columns, two FKs
(`students.id`, `ml_model_version.id`) instead of zero.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ml_prediction",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id"),
            nullable=False,
        ),
        sa.Column(
            "model_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ml_model_version.id"),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ml_prediction_student_id", "ml_prediction", ["student_id"])
    op.create_index("ix_ml_prediction_model_version_id", "ml_prediction", ["model_version_id"])


def downgrade() -> None:
    op.drop_index("ix_ml_prediction_model_version_id", table_name="ml_prediction")
    op.drop_index("ix_ml_prediction_student_id", table_name="ml_prediction")
    op.drop_table("ml_prediction")
