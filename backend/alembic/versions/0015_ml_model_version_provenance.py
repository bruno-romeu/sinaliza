"""ml_model_version: training_dataset_version, feature_schema_version, metrics

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-04

`AGENTS.md` §"Versionamento de modelo" exige persistir seis campos por versão
de modelo; a tabela criada em 0011 persistia quatro. Esta migration acrescenta
os três que faltavam.

As três colunas são `NULL`-áveis e **não há backfill**, deliberadamente: uma
linha gravada antes desta migration não tem como saber qual fingerprint de
dataset a treinou nem sob qual esquema de features, e escrever um valor
plausível ali seria procedência fabricada — exatamente o oposto do que a
coluna existe para sustentar. `NULL` significa "não registrado", e o código de
inferência trata esse caso explicitamente (`app/ml/predict.py` pula a
verificação de esquema quando a coluna é nula, em vez de recusar o artefato).

`metrics` é `JSONB` e não `JSON` para que o relatório seja consultável por
campo (`metrics->>'f1'`) sem reparsear texto. Quem escreve é
`python -m app.ml.evaluate`, nunca o treino: treinar e avaliar no mesmo
conjunto é proibido (`AGENTS.md` §Atalhos proibidos), então a métrica só passa
a existir depois de uma avaliação sobre o corte `EVAL_DEMO`.

Sem enum novo, então nenhum ciclo `CREATE TYPE`/`DROP TYPE` para administrar —
`downgrade()` é a remoção simétrica das três colunas.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ml_model_version",
        sa.Column("training_dataset_version", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "ml_model_version",
        sa.Column("feature_schema_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "ml_model_version",
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ml_model_version", "metrics")
    op.drop_column("ml_model_version", "feature_schema_version")
    op.drop_column("ml_model_version", "training_dataset_version")
