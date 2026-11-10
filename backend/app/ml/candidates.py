"""Os modelos candidatos que `python -m app.ml.compare` mede uns contra os
outros (spec-comparacao-de-modelos-baseline).

O `AGENTS.md` §Modelos manda "começar simples... comparar antes de adicionar
modelos complexos". Este módulo é a lista do que entra nessa comparação, e o
lugar onde cada escolha está justificada por escrito — a pergunta "por que
floresta aleatória?" é respondida por uma medição contra estes candidatos, não
por preferência.

Cada candidato é um `Pipeline` **inteiro** (pré-processamento + classificador),
nunca um classificador solto. O que se compara é a coisa que seria colocada em
produção, e o pré-processamento faz parte dela: medir classificadores nus sob
um pré-processamento comum compararia uma configuração que ninguém usaria.

`random_state=42` em todo candidato estocástico (inclusive o `DummyClassifier`
`stratified`, que sorteia): a comparação precisa dar o mesmo resultado quando
alguém a reexecutar na defesa.

Nenhum modelo de gradient boosting aparece aqui. O `AGENTS.md` §"Atalhos
proibidos" veda XGBoost/LightGBM nominalmente, e a regra é anterior à medição:
não é "medimos e não precisou", é "não é para adicionar".
"""

from __future__ import annotations

from collections.abc import Callable

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.feature_aggregation import FEATURE_COLUMNS
from app.ml.pipeline import build_pipeline

#: Mesma derivação de `app/ml/pipeline.py`: o número de colunas vem de
#: `FEATURE_COLUMNS`, nunca escrito à mão.
_NUMERIC_FEATURE_COUNT = len(FEATURE_COLUMNS)

RANDOM_STATE = 42


def _imputer_only_preprocessor() -> ColumnTransformer:
    """O pré-processamento do pipeline de produção: só imputação pela média.
    Suficiente para modelos baseados em árvore, que são invariantes a escala
    monotônica."""
    return ColumnTransformer(
        transformers=[
            (
                "numeric",
                # Mesma razão de `app/ml/pipeline.py`: sem a flag, uma coluna
                # inteiramente ausente no ajuste é descartada e o pipeline
                # deixa de ter a largura que `FEATURE_COLUMNS` declara.
                SimpleImputer(strategy="mean", keep_empty_features=True),
                list(range(_NUMERIC_FEATURE_COUNT)),
            ),
        ]
    )


def _imputer_and_scaler_preprocessor() -> ColumnTransformer:
    """Imputação **mais** padronização.

    `LogisticRegression` é sensível à escala das entradas, e as features
    convivem em escalas incompatíveis: taxas em `[0, 1]`, notas em `[0, 10]`,
    contagens inteiras sem teto. Sem padronizar, o termo de regularização L2
    (ligado por padrão) penaliza desproporcionalmente os coeficientes das
    colunas de menor amplitude, e o solver converge mal — a regressão sairia
    pior por motivo de escala, não por capacidade.

    Comparar a floresta contra uma regressão logística não-escalonada seria
    pesar um lado da balança e chamar o resultado de evidência."""
    return ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="mean", keep_empty_features=True)),
                        ("scaler", StandardScaler()),
                    ]
                ),
                list(range(_NUMERIC_FEATURE_COUNT)),
            ),
        ]
    )


def _build_dummy_most_frequent() -> Pipeline:
    """O piso degenerado: responde sempre a classe majoritária (`STABLE`, 70%
    da base por `SYNTHETIC_PROFILE_PROPORTIONS`).

    Está aqui para tornar **medido** o argumento que `docs/model-evaluation.md`
    §4 fazia só no papel: este classificador marca ~0,70 de Accuracy sem ter
    reconhecido padrão nenhum, enquanto seu F1 macro desaba. É a demonstração
    de por que o `AGENTS.md` veda escolher modelo por Accuracy.

    `prior` não entra como um terceiro candidato: em predição dura ele é
    idêntico a este (difere apenas em `predict_proba`), e uma linha repetindo
    os números de outra linha é ruído na tabela."""
    return Pipeline(
        steps=[
            ("preprocessor", _imputer_only_preprocessor()),
            ("classifier", DummyClassifier(strategy="most_frequent")),
        ]
    )


def _build_dummy_stratified() -> Pipeline:
    """O piso honesto para uma métrica macro: sorteia respeitando as
    proporções de classe observadas no treino.

    `most_frequent` é degenerado para média macro — três das quatro classes
    recebem F1 zero por construção, então qualquer modelo o supera sem provar
    nada. `stratified` acerta cada classe na taxa do acaso informado pelas
    proporções, que é o nulo contra o qual "o modelo aprendeu alguma coisa"
    precisa ser demonstrado. Os dois entram porque respondem perguntas
    diferentes."""
    return Pipeline(
        steps=[
            ("preprocessor", _imputer_only_preprocessor()),
            (
                "classifier",
                DummyClassifier(strategy="stratified", random_state=RANDOM_STATE),
            ),
        ]
    )


def _build_logistic_regression() -> Pipeline:
    """O modelo simples que o `AGENTS.md` §Modelos nomeia.

    `max_iter=1000` (o padrão do sklearn é 100): com quatro classes e features
    padronizadas, 100 iterações podem terminar em `ConvergenceWarning`, e um
    modelo que não convergiu mede o orçamento de iteração, não a família de
    modelo. Demais hiperparâmetros nos padrões — não há busca aqui, por
    decisão da spec (Non-goals)."""
    return Pipeline(
        steps=[
            ("preprocessor", _imputer_and_scaler_preprocessor()),
            (
                "classifier",
                LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
            ),
        ]
    )


#: Os candidatos, em ordem de leitura: pisos primeiro, depois o simples, por
#: último o que está em produção. A ordem é a do argumento — "isto é o acaso,
#: isto é o simples, e aqui está o que usamos" —, não a ordem do resultado.
#:
#: `random_forest` é construído por `build_pipeline()`, a função de produção
#: em pessoa. Uma réplica da floresta declarada aqui poderia divergir da que
#: `train.py` serializa, e a comparação passaria a medir um modelo que não é o
#: que roda.
CANDIDATE_BUILDERS: tuple[tuple[str, Callable[[], Pipeline]], ...] = (
    ("dummy_most_frequent", _build_dummy_most_frequent),
    ("dummy_stratified", _build_dummy_stratified),
    ("logistic_regression", _build_logistic_regression),
    ("random_forest", build_pipeline),
)

CANDIDATE_NAMES: tuple[str, ...] = tuple(name for name, _builder in CANDIDATE_BUILDERS)


def build_candidate(name: str) -> Pipeline:
    """Um candidato não-ajustado pelo nome. `KeyError` para nome desconhecido
    — a lista é fechada."""
    for candidate_name, builder in CANDIDATE_BUILDERS:
        if candidate_name == name:
            return builder()
    raise KeyError(f"Unknown candidate {name!r}. Known: {', '.join(CANDIDATE_NAMES)}.")
