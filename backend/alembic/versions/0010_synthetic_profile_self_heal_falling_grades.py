"""self-heal synthetic_profile enum: add FALLING_GRADES if missing

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-15

0006_create_synthetic_generation_runs_table.py was amended in place during
Story 2.2 to add FALLING_GRADES to the synthetic_profile enum literal,
violating the project's "never amend an already-applied migration"
convention. Alembic tracks applied revisions by id, not file content, so a
database that already ran revision 0006 while it still had only 3 members
(STABLE, FALLING_ATTENDANCE, COMBINED_DETERIORATION) never re-runs it and is
permanently stuck without FALLING_GRADES. This migration self-heals that
case; on a database where 0006 already created all 4 labels, it's a no-op.

`env.py` wraps every pending migration in a *single* transaction per
`alembic upgrade` invocation (not one transaction per migration), so
`ADD VALUE` runs inside `op.get_context().autocommit_block()` to commit it
immediately — otherwise a later migration added to this same chain that
uses 'FALLING_GRADES' in the same `upgrade head` run (e.g. a backfill)
would hit Postgres's "unsafe use of new value of enum type" (new enum
labels can't be used in the transaction that added them) (code review
finding, this spec).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE synthetic_profile ADD VALUE IF NOT EXISTS 'FALLING_GRADES'")


def downgrade() -> None:
    # Postgres has no native "drop enum value" — this migration is a
    # one-way safety backstop, not a schema element to reverse.
    pass
