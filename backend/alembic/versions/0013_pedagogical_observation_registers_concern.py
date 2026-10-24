"""add registers_concern to pedagogical_observations

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-24

spec-ui-3: an observation only counts as a convergence signal when whoever
wrote it marked it as registering a concern. Neutral observations ("Frequência
dentro da faixa habitual") stay as evidence and in the timeline, never as a
signal. Existing rows default to `false`; regenerate the synthetic base to get
the generator's own flags.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pedagogical_observations",
        sa.Column(
            "registers_concern",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("pedagogical_observations", "registers_concern")
