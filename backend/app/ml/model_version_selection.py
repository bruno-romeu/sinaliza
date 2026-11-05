"""Qual `MLModelVersion` usar — a única seleção que `app/ml/predict.py` e
`app/ml/evaluate.py` fazem.

Os dois CLIs carregavam a mesma query ("a mais recente por `trained_at desc`,
desempate por `id desc`") escrita duas vezes, e nenhum dos dois sabia pontuar ou
avaliar com uma versão específica. A procedência passou a ser persistida
(`training_dataset_version`, `feature_schema_version`, `metrics`), mas a
pergunta "reavalie **este** modelo" não tinha comando que a respondesse.

`version` já é `UNIQUE` em `ml_model_version`, então selecionar por ela não
exige coluna nem índice novo. Sem `version`, o comportamento é byte a byte o
anterior — a seleção explícita é um acréscimo, nunca uma troca do padrão.

Esta seleção **não** é uma permissão: escolher a versão diz *qual* artefato
usar, nunca *apesar de quê*. `require_matching_feature_schema()` continua
rodando depois, no chamador, e recusa um artefato treinado sob outro esquema de
features mesmo quando foi pedido pelo nome.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import MLModelVersionModel


class ModelVersionNotFoundError(RuntimeError):
    """Levantada quando `--model-version` nomeia uma `version` que não existe.
    Distinta de `NoModelVersionError` (tabela vazia) de propósito: "você pediu
    uma versão que não existe" e "não há modelo nenhum treinado" pedem ações
    diferentes de quem rodou o comando."""


def select_model_version(session: Session, version: str | None) -> MLModelVersionModel | None:
    """A `MLModelVersion` pedida por `version`, ou a mais recente quando
    `version is None`. Devolve `None` quando não há linha — traduzir esse `None`
    em erro é do chamador, porque a mensagem difere entre pontuar e avaliar."""
    query = select(MLModelVersionModel)
    if version is not None:
        query = query.where(MLModelVersionModel.version == version)
    return session.execute(
        query.order_by(MLModelVersionModel.trained_at.desc(), MLModelVersionModel.id.desc()).limit(
            1
        )
    ).scalar_one_or_none()


def model_version_not_found_message(version: str) -> str:
    return (
        f"No MLModelVersion with version={version!r} was found. "
        "List the available versions with "
        "`SELECT version, trained_at FROM ml_model_version ORDER BY trained_at DESC;` "
        "or train a new one with `python -m app.ml.train`."
    )
