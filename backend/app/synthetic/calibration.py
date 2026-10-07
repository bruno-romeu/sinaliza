"""Constantes de calibração do gerador de dataset sintético (Story 2.4).

Este módulo é **puro**: nenhuma chamada de rede, nenhum acesso a banco,
nenhuma leitura de arquivo. A base pública de referência (INEP/IBGE) é
consultada **offline**, por um humano, no momento de calibrar estes números —
nunca em tempo de execução, e nunca persistida no banco do sistema
(`epic-2-context.md` §Requirements & Constraints; AC 2 da Story 2.4).

A pesquisa que origina estes valores está em
`docs/research/technical-bases-publicas-dados-educacionais-calibr-2026-09-17/research.md`
e chegou a **três veredictos distintos**, que este módulo mantém distintos:

1. **Calibrável, confiança alta** — abandono/evasão/reprovação do Censo
   Escolar 2023. `ParameterKind.CALIBRATED`.
2. **Só proxy, confiança média** — a distribuição de notas. Não existe fonte
   pública brasileira de notas de boletim 0–10; os 4 níveis de proficiência
   do SAEB são o único proxy, e a distribuição 0–10 resultante é uma
   **suposição de design documentada**, não dado calibrado.
   `ParameterKind.DESIGN_ASSUMPTION`, ancorada num
   `ParameterKind.PUBLIC_REFERENCE`.
3. **Suposição de design pura, sem fonte alguma** — frequência diária e
   não-entrega de atividades. Nenhuma base pública brasileira mede nem uma
   nem outra. `ParameterKind.DESIGN_ASSUMPTION` com `Confidence.NONE`.

Regra de leitura: `kind` diz *o que o número é*; `confidence` diz *quanto
confiar na fonte*. Um número pode ter confiança média e ainda assim ser uma
suposição de design (é o caso de `GRADE_DISTRIBUTION`).

Este módulo é **insumo** do gerador, não consumidor: ele não importa
`app.synthetic.generate` nem qualquer outro módulo da Story 2.1, e é
importável e testável sozinho.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Vocabulário de proveniência
# ---------------------------------------------------------------------------


class Confidence(str, Enum):
    """Quanta confiança a fonte sustenta.

    `NONE` não é "baixa": é a ausência de qualquer medição. Usar `LOW` ali
    sugeriria uma medição fraca, e não existe medição nenhuma. Todo parâmetro
    carrega um nível — inclusive os que não têm fonte.
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class ParameterKind(str, Enum):
    """O que o número é, em termos de origem."""

    #: Valor retirado de uma estatística pública brasileira.
    CALIBRATED = "CALIBRATED"
    #: Estatística pública registrada apenas como referência de ordem de
    #: grandeza. NUNCA usada como parâmetro de geração
    #: (`used_by_generator=False`).
    PUBLIC_REFERENCE = "PUBLIC_REFERENCE"
    #: Nenhuma base pública brasileira mede esta variável. O valor é uma
    #: decisão de modelagem, assumida e documentada como tal.
    DESIGN_ASSUMPTION = "DESIGN_ASSUMPTION"
    #: Imposto pelo schema do próprio Sinaliza (Epic 1), não por fonte
    #: externa — não é calibração nem suposição.
    SYSTEM_INVARIANT = "SYSTEM_INVARIANT"


#: Texto padrão de `source` para as variáveis que simplesmente não têm fonte
#: pública brasileira. Registrar a ausência explicitamente é o que impede uma
#: suposição de virar "fato" silenciosamente na base de código
#: (`research.md` §Recomendações, item 5).
NO_PUBLIC_SOURCE = (
    "Sem fonte pública brasileira: nenhuma base federal, estadual ou "
    "agregadora (INEP, IBGE, QEdu) mede esta variável "
    "(research.md §3 e §Recomendações, item 3). Valor é suposição de design."
)


@dataclass(frozen=True)
class GradeBand:
    """Uma faixa da escala 0–10 e a fração de notas desenhada nela.

    `min_value`/`max_value` são `Decimal` para casar com `Grade.value`
    (`app/domain/grade.py`), que é `Decimal` na escala 0.0–10.0.
    """

    label: str
    min_value: Decimal
    max_value: Decimal
    share: float


@dataclass(frozen=True, eq=False)
class CalibrationParameter:
    """Um parâmetro de geração com sua proveniência anexada como *dado*.

    `eq=False` (identidade) de propósito: estes objetos são singletons de
    módulo, e alguns `value` são mappings — com a igualdade estrutural
    padrão o dataclass ficaria inhashável e não poderia entrar num `set`.

    Proveniência registrada só em comentário não pode ser testada, e um
    requisito não testado apodrece em silêncio. Cada campo abaixo é asserido
    por `backend/tests/test_synthetic_calibration.py`.
    """

    #: Deve ser idêntico ao nome do símbolo de módulo (testado).
    name: str
    #: O valor em si: float, tupla (faixa), tupla de `GradeBand`, ou mapping.
    value: Any
    #: `"proportion"` | `"grade_points_0_10"` | `"grade_band_distribution"`.
    unit: str
    #: O que a variável significa. Crítico para abandono vs. evasão, que são
    #: métricas diferentes e nunca devem ser somadas.
    definition: str
    #: Fonte pública — ou a declaração explícita de que não existe fonte.
    #: Nunca vazio.
    source: str
    #: Índices do "Apêndice de fontes" de `research.md`.
    source_refs: tuple[str, ...]
    confidence: Confidence
    kind: ParameterKind
    #: `False` para números registrados apenas como referência: eles
    #: aparecem aqui para que um revisor os encontre, não para alimentar o
    #: gerador.
    used_by_generator: bool
    #: Raciocínio, ressalvas e o que explicitamente NÃO se pode concluir.
    rationale: str

    @property
    def is_design_assumption(self) -> bool:
        """`True` quando o valor é decisão de modelagem, não dado calibrado."""
        return self.kind is ParameterKind.DESIGN_ASSUMPTION


# ---------------------------------------------------------------------------
# 1. Calibrável, confiança alta — Censo Escolar 2023
#
# Abandono e evasão são DUAS VARIÁVEIS DISTINTAS e não devem ser somadas:
# o INEP define abandono como situação de fim de ano (dentro do Censo) e
# evasão como taxa de transição (o aluno não se rematricula no ano seguinte,
# mesmo sem ter sido classificado como abandono) [22]. Elas medem coisas
# diferentes, em momentos diferentes, e somá-las produziria um número sem
# significado.
# ---------------------------------------------------------------------------

ABANDONMENT_RATE_EF = CalibrationParameter(
    name="ABANDONMENT_RATE_EF",
    value=0.030,
    unit="proportion",
    definition=(
        "Taxa de ABANDONO no Ensino Fundamental: proporção de alunos "
        "registrados na situação final do Censo Escolar como tendo deixado "
        "de frequentar durante o ano letivo. É uma situação de fim de ano, "
        "medida dentro do próprio ano — não é evasão."
    ),
    source="Censo Escolar 2023 (MEC/INEP, 22/02/2024), corroborado pela Fundação Carlos Chagas",
    source_refs=("[20]", "[21]"),
    confidence=Confidence.HIGH,
    kind=ParameterKind.CALIBRATED,
    used_by_generator=True,
    rationale=(
        "Verificado por duas fontes independentes (comunicado oficial "
        "MEC/INEP + FCC). Ressalva registrada em research.md: nenhuma tabela "
        "primária do INEP foi lida linha a linha para reconciliar "
        "exaustivamente abandono e evasão por etapa/ano — o mecanismo "
        "conceitual está confirmado, o cruzamento fino não."
    ),
)

EVASION_RATE_EM = CalibrationParameter(
    name="EVASION_RATE_EM",
    value=0.059,
    unit="proportion",
    definition=(
        "Taxa de EVASÃO no Ensino Médio: taxa de transição — o aluno não se "
        "rematricula no ano seguinte, mesmo sem ter sido classificado como "
        "abandono. Mede o intervalo entre dois anos letivos, não o ano "
        "corrente. Não é a mesma métrica que ABANDONMENT_RATE_EF e jamais "
        "deve ser somada a ela."
    ),
    source="Censo Escolar 2023 (MEC/INEP), com a distinção abandono/evasão documentada pelo INEP",
    source_refs=("[20]", "[21]", "[22]"),
    confidence=Confidence.HIGH,
    kind=ParameterKind.CALIBRATED,
    used_by_generator=True,
    rationale=(
        "A evasão é sistematicamente maior que o abandono no mesmo período "
        "(recorte 2019/2020: abandono 4,7% vs. evasão 6,9%), o que confirma "
        "que são indicadores distintos e não recortes do mesmo número."
    ),
)

FAILURE_RATE_EM = CalibrationParameter(
    name="FAILURE_RATE_EM",
    value=0.039,
    unit="proportion",
    definition=(
        "Taxa de REPROVAÇÃO no Ensino Médio: proporção de alunos com "
        "situação final de reprovado no Censo Escolar. Distinta tanto de "
        "abandono quanto de evasão."
    ),
    source="Censo Escolar 2023 (MEC/INEP), corroborado pela Fundação Carlos Chagas",
    source_refs=("[20]", "[21]"),
    confidence=Confidence.HIGH,
    kind=ParameterKind.CALIBRATED,
    used_by_generator=True,
    rationale=(
        "Metodologia oficial das taxas de rendimento fixada pelo INEP desde "
        "2010 e sem alteração relevante desde então [13]."
    ),
)

COMBINED_FAILURE_RATE_EM_FIRST_YEAR = CalibrationParameter(
    name="COMBINED_FAILURE_RATE_EM_FIRST_YEAR",
    value=(0.164, 0.213),
    unit="proportion",
    definition=(
        "Faixa de INSUCESSO ESCOLAR COMBINADO (reprovação + abandono, tal "
        "como a própria fonte publica o indicador) no 1º ano do Ensino "
        "Médio: 16,4% em 2023 e 21,3% em 2019. É o subgrupo de risco "
        "elevado da educação básica brasileira. ATENÇÃO: a combinação aqui "
        "é reprovação+abandono, feita e publicada pela fonte — NÃO é a soma "
        "de abandono com evasão, que permanece proibida."
    ),
    source="Fundação Carlos Chagas a partir do Censo Escolar (série 2019–2023)",
    source_refs=("[20]",),
    confidence=Confidence.HIGH,
    kind=ParameterKind.CALIBRATED,
    used_by_generator=True,
    rationale=(
        "O valor de 2020 na mesma série (6,4%) é outlier pandêmico "
        "(promoção quase automática) e foi deliberadamente excluído da "
        "faixa — o próprio INEP recomenda cautela na leitura da série "
        "nesses anos [25][28]. Séries vizinhas, para contexto: 3º ano EF "
        "6,8% e 6º ano EF 8,7% em 2023."
    ),
)

# ---------------------------------------------------------------------------
# 2. Referências públicas — registradas, NUNCA usadas como parâmetro
#
# Estes números existem aqui porque são exatamente os que um revisor vai
# procurar. `used_by_generator=False` declara, em dado, que eles não
# alimentam o gerador.
# ---------------------------------------------------------------------------

SAEB_INSUFFICIENT_SHARE_MATH_FINAL_YEAR = CalibrationParameter(
    name="SAEB_INSUFFICIENT_SHARE_MATH_FINAL_YEAR",
    value=0.59,
    unit="proportion",
    definition=(
        "Proporção de estudantes no nível 'Insuficiente' em Matemática no "
        "último ano da educação básica, SAEB 2023. O SAEB mede proficiência "
        "numa escala de pontos com 4 níveis categóricos "
        "(insuficiente/básico/proficiente/avançado) — NÃO é nota de boletim "
        "e não está na escala 0–10."
    ),
    source="Relatório SAEB 2023 Volume 1 (INEP), via cobertura secundária",
    source_refs=("[23]",),
    confidence=Confidence.MEDIUM,
    kind=ParameterKind.PUBLIC_REFERENCE,
    used_by_generator=False,
    rationale=(
        "Confiança média: o PDF primário do INEP não pôde ser aberto (erro "
        "de certificado SSL) em nenhuma das duas rodadas de pesquisa; o "
        "número vem de cobertura secundária. É a ÂNCORA de "
        "GRADE_DISTRIBUTION, não um parâmetro de geração: a conversão de "
        "nível de proficiência para nota 0–10 é desenhada, não observada."
    ),
)

PNAD_ADJUSTED_NET_ATTENDANCE_RATE_EF = CalibrationParameter(
    name="PNAD_ADJUSTED_NET_ATTENDANCE_RATE_EF",
    value=(0.989, 1.000),
    unit="proportion",
    definition=(
        "Taxa de FREQUÊNCIA LÍQUIDA AJUSTADA no Ensino Fundamental (PNAD "
        "Contínua). Mede adequação idade-etapa — ou seja, ACESSO E "
        "PERMANÊNCIA NA ESCOLA NA IDADE CERTA. NÃO mede presença diária em "
        "sala de aula."
    ),
    source="PNAD Contínua — módulo Educação (IBGE)",
    source_refs=("[9]",),
    confidence=Confidence.MEDIUM,
    kind=ParameterKind.PUBLIC_REFERENCE,
    used_by_generator=False,
    rationale=(
        "Registrada apenas como referência de ordem de grandeza. Usá-la "
        "como proxy de frequência diária produziria uma taxa de presença "
        "artificialmente inflada e sem relação com 'faltas consecutivas', "
        "que é o sinal que o Sinaliza precisa detectar "
        "(research.md §3 e §Recomendações, item 3). Por isso "
        "`used_by_generator=False`."
    ),
)

PNAD_ADJUSTED_NET_ATTENDANCE_RATE_EM = CalibrationParameter(
    name="PNAD_ADJUSTED_NET_ATTENDANCE_RATE_EM",
    value=0.806,
    unit="proportion",
    definition=(
        "Taxa de FREQUÊNCIA LÍQUIDA AJUSTADA no Ensino Médio (PNAD "
        "Contínua). Mesmo conceito de adequação idade-etapa do parâmetro "
        "acima — acesso, não assiduidade diária."
    ),
    source="PNAD Contínua — módulo Educação (IBGE)",
    source_refs=("[9]",),
    confidence=Confidence.MEDIUM,
    kind=ParameterKind.PUBLIC_REFERENCE,
    used_by_generator=False,
    rationale=(
        "Mesma ressalva de PNAD_ADJUSTED_NET_ATTENDANCE_RATE_EF: referência "
        "de ordem de grandeza, nunca parâmetro de frequência diária."
    ),
)

# ---------------------------------------------------------------------------
# 3. Distribuição de notas — SUPOSIÇÃO DE DESIGN ancorada num proxy
# ---------------------------------------------------------------------------

GRADE_DISTRIBUTION = CalibrationParameter(
    name="GRADE_DISTRIBUTION",
    value=(
        GradeBand("Insuficiente", Decimal("0.0"), Decimal("4.9"), 0.59),
        GradeBand("Básico", Decimal("5.0"), Decimal("6.9"), 0.24),
        GradeBand("Proficiente", Decimal("7.0"), Decimal("8.4"), 0.13),
        GradeBand("Avançado", Decimal("8.5"), Decimal("10.0"), 0.04),
    ),
    unit="grade_band_distribution",
    definition=(
        "Distribuição sintética de notas na escala 0–10, em 4 faixas "
        "nomeadas segundo os níveis de proficiência do SAEB. As faixas não "
        "se sobrepõem e as frações somam 1,0; os limites são "
        "deliberadamente separados por 0,1 (4.9|5.0, 6.9|7.0, 8.4|8.5) para "
        "que cada faixa seja inequívoca mesmo que `grades.value` (Numeric "
        "4,2) um dia receba um valor sintético com duas casas decimais — "
        "não é uma partição exaustiva de toda a escala em duas casas."
    ),
    source=(
        "SAEB 2023 usado como PROXY CATEGÓRICO (~59% em 'Insuficiente' em "
        "Matemática no fim da educação básica). Não existe fonte pública "
        "brasileira para distribuição de notas de boletim 0–10 — nem o "
        "Censo Escolar nem o INEP coletam ou publicam notas."
    ),
    source_refs=("[23]",),
    confidence=Confidence.MEDIUM,
    kind=ParameterKind.DESIGN_ASSUMPTION,
    used_by_generator=True,
    rationale=(
        "SUPOSIÇÃO DE DESIGN, não dado calibrado. Apenas a fração 0,59 da "
        "faixa 'Insuficiente' está ancorada numa estatística pública. Os "
        "pontos de corte em 0–10 e a repartição dos 0,41 restantes "
        "(0,24 / 0,13 / 0,04, decrescente, com 'Avançado' como minoria "
        "pequena, na forma conhecida da distribuição do SAEB) foram "
        "DESENHADOS por este projeto. A confiança MÉDIA se refere à âncora "
        "(fonte secundária sobre PDF primário inacessível), não à conversão "
        "para 0–10, que não tem confiança estatística alguma."
    ),
)

# ---------------------------------------------------------------------------
# 4. Frequência diária e entrega de atividades — SUPOSIÇÃO DE DESIGN PURA
#
# Nenhuma base pública brasileira mede assiduidade cotidiana nem entrega de
# tarefas. Isso não é lacuna de busca: é estrutural — o Censo Escolar mede
# matrícula/situação final, o SAEB mede proficiência amostral, a PNAD mede
# adequação idade-etapa. Nenhuma delas foi desenhada para medir isto.
# ---------------------------------------------------------------------------

DAILY_ATTENDANCE_RATE_BASELINE = CalibrationParameter(
    name="DAILY_ATTENDANCE_RATE_BASELINE",
    value=0.95,
    unit="proportion",
    definition=(
        "Proporção esperada de dias letivos com presença, para um estudante "
        "sintético de trajetória estável. Conta presente vs. ausente; o "
        "recorte justificada/injustificada de `AttendanceStatus` não é "
        "calibrado aqui (RF-11 conta as duas igualmente no MVP)."
    ),
    source=NO_PUBLIC_SOURCE,
    source_refs=(),
    confidence=Confidence.NONE,
    kind=ParameterKind.DESIGN_ASSUMPTION,
    used_by_generator=True,
    rationale=(
        "Valor escolhido por este projeto, não medido. Âncora de ordem de "
        "grandeza: a LDB (Lei 9.394/1996, art. 24, VI) exige frequência "
        "mínima de 75% para aprovação — um limiar NORMATIVO, não uma "
        "distribuição observada, usado só para situar um estudante estável "
        "confortavelmente acima dele. A frequência líquida ajustada da PNAD "
        "foi deliberadamente NÃO usada aqui (ver "
        "PNAD_ADJUSTED_NET_ATTENDANCE_RATE_EF)."
    ),
)

DAILY_ATTENDANCE_RATE_AT_RISK_FLOOR = CalibrationParameter(
    name="DAILY_ATTENDANCE_RATE_AT_RISK_FLOOR",
    value=0.60,
    unit="proportion",
    definition=(
        "Piso de frequência ao qual uma trajetória em deterioração converge "
        "ao fim do ano letivo sintético. A regra de decaimento em si "
        "pertence aos perfis da Story 2.2; aqui fica apenas o piso."
    ),
    source=NO_PUBLIC_SOURCE,
    source_refs=(),
    confidence=Confidence.NONE,
    kind=ParameterKind.DESIGN_ASSUMPTION,
    used_by_generator=True,
    rationale=(
        "Valor escolhido por este projeto, não medido. Deliberadamente "
        "abaixo do limiar normativo de 75% da LDB, para que a trajetória "
        "sintética efetivamente atravesse a faixa em que uma coordenação "
        "pedagógica real agiria — sem isso, a queda seria visível no "
        "gráfico mas inconsequente."
    ),
)

ASSIGNMENT_NON_DELIVERY_RATE_BASELINE = CalibrationParameter(
    name="ASSIGNMENT_NON_DELIVERY_RATE_BASELINE",
    value=0.08,
    unit="proportion",
    definition=(
        "Proporção de atividades com status NOT_DELIVERED para um estudante "
        "sintético de trajetória estável."
    ),
    source=NO_PUBLIC_SOURCE,
    source_refs=(),
    confidence=Confidence.NONE,
    kind=ParameterKind.DESIGN_ASSUMPTION,
    used_by_generator=True,
    rationale=(
        "Valor escolhido por este projeto, não medido. 'Atividades não "
        "entregues' é dado operacional interno de sistemas de gestão "
        "escolar (LMS, SEDs estaduais), nunca consolidado nacionalmente — "
        "confirmado nas duas rodadas de todas as dimensões da pesquisa. A "
        "fração DELIVERED é derivada pelo gerador: "
        "1 - NON_DELIVERY - PARTIAL."
    ),
)

ASSIGNMENT_PARTIAL_DELIVERY_RATE_BASELINE = CalibrationParameter(
    name="ASSIGNMENT_PARTIAL_DELIVERY_RATE_BASELINE",
    value=0.07,
    unit="proportion",
    definition=(
        "Proporção de atividades com status PARTIAL para um estudante "
        "sintético de trajetória estável. Existe porque "
        "`AssignmentSubmissionStatus` da Epic 1 é tri-estado; o gerador "
        "nunca deve produzir um estado que o schema não comporta."
    ),
    source=NO_PUBLIC_SOURCE,
    source_refs=(),
    confidence=Confidence.NONE,
    kind=ParameterKind.DESIGN_ASSUMPTION,
    used_by_generator=True,
    rationale="Valor escolhido por este projeto, não medido. Mesma ausência de fonte.",
)

ASSIGNMENT_NON_DELIVERY_RATE_AT_RISK_CEILING = CalibrationParameter(
    name="ASSIGNMENT_NON_DELIVERY_RATE_AT_RISK_CEILING",
    value=0.50,
    unit="proportion",
    definition=(
        "Teto de não-entrega ao qual uma trajetória em deterioração "
        "converge ao fim do ano letivo sintético."
    ),
    source=NO_PUBLIC_SOURCE,
    source_refs=(),
    confidence=Confidence.NONE,
    kind=ParameterKind.DESIGN_ASSUMPTION,
    used_by_generator=True,
    rationale=(
        "Valor escolhido por este projeto, não medido. Escolhido para que a "
        "não-entrega seja um sinal independente e detectável, e não apenas "
        "ruído sobre a linha de base."
    ),
)

# ---------------------------------------------------------------------------
# 5. Proporções de perfil — SUPOSIÇÃO DE DESIGN, deliberadamente enriquecida
# ---------------------------------------------------------------------------

SYNTHETIC_PROFILE_PROPORTIONS = CalibrationParameter(
    name="SYNTHETIC_PROFILE_PROPORTIONS",
    value=MappingProxyType(
        {
            "STABLE": 0.70,
            "FALLING_ATTENDANCE": 0.12,
            "FALLING_GRADES": 0.08,
            "COMBINED_DETERIORATION": 0.10,
        }
    ),
    unit="proportion",
    definition=(
        "Fração da base sintética atribuída a cada perfil de trajetória. As "
        "chaves são strings de propósito: o enum `SyntheticProfile` pertence "
        "à Story 2.2, e este módulo é insumo dela, não consumidor. A "
        "paridade chave↔enum é responsabilidade da Story 2.2."
    ),
    source=(
        "Sem fonte pública: nenhuma base brasileira mede 'proporção de "
        "estudantes com trajetória em deterioração'. As taxas do Censo "
        "medem DESFECHO (abandono/evasão/reprovação), não MUDANÇA DE "
        "TRAJETÓRIA observável durante o ano."
    ),
    source_refs=(),
    confidence=Confidence.NONE,
    kind=ParameterKind.DESIGN_ASSUMPTION,
    used_by_generator=True,
    rationale=(
        "ENRIQUECIMENTO DELIBERADO, registrado para ser auditável. A taxa "
        "de abandono do Censo (~3% no EF) daria ~6 estudantes em "
        "deterioração numa base de ~200 — poucos demais para o Epic 3 "
        "validar a regra de convergência do RF-11 e para o Epic 5 treinar e "
        "avaliar. Os 30% não-estáveis aqui são uma decisão de modelagem, "
        "não uma taxa observada; a taxa real segue visível em "
        "ABANDONMENT_RATE_EF, de modo que a inflação fica auditável em vez "
        "de escondida. Consequência a declarar no Epic 5: a prevalência de "
        "classe positiva deste dataset NÃO é a prevalência brasileira, e "
        "nenhuma métrica medida sobre ele pode ser lida como desempenho no "
        "mundo real (AGENTS.md §Avaliação de ML)."
    ),
)

# ---------------------------------------------------------------------------
# 6. Proporção do split TRAIN/EVAL_DEMO — SUPOSIÇÃO DE DESIGN PURA (Story 2.3)
#
# Nenhuma base pública mede "proporção ideal de treino/avaliação para um
# dataset escolar sintético" — não é um fenômeno pedagógico a calibrar, é uma
# decisão de metodologia de machine learning. Fica registrada aqui, com a
# mesma disciplina de proveniência dos demais parâmetros, em vez de viver
# como um número mágico embutido em `GenerationConfig`/no `argparse` do CLI
# (epic-2-context.md AD-4; `docs/epics.md` Story 2.3, AC "proporção...
# documentada explicitamente... como constante nomeada").
# ---------------------------------------------------------------------------

TRAIN_EVAL_SPLIT_RATIO = CalibrationParameter(
    name="TRAIN_EVAL_SPLIT_RATIO",
    value=0.7,
    unit="proportion",
    definition=(
        "Fração da base sintética atribuída ao recorte TRAIN; o restante "
        "(1 - este valor) vai para EVAL_DEMO (AD-4). TRAIN alimenta somente "
        "o treino offline do modelo do Epic 5 e nunca é servido pela "
        "aplicação web; EVAL_DEMO recebe trajetória completa ao longo de "
        "todo o ano letivo sintético e é o único recorte lido em tempo de "
        "execução (home/trajetória/lançamento), via o filtro "
        "`dataset_split = EVAL_DEMO` de `repositories/base.py` (AD-11)."
    ),
    source=NO_PUBLIC_SOURCE,
    source_refs=(),
    confidence=Confidence.NONE,
    kind=ParameterKind.DESIGN_ASSUMPTION,
    used_by_generator=True,
    rationale=(
        "Decisão de modelagem de ML, não dado calibrado. 0.7/0.3 é a "
        "convenção usual de split de dataset (maioria dos dados para "
        "treino, uma fatia substancial reservada para avaliação), aplicada "
        "a uma base de ~200 estudantes: ~140 em TRAIN dão ao Epic 5 volume "
        "suficiente para treinar um classificador, e ~60 em EVAL_DEMO "
        "bastam tanto para uma avaliação estatisticamente informativa "
        "quanto para popular a demonstração ao vivo do produto sem esvaziar "
        "o treino. `population.py`/`generate.py` consomem este valor como "
        "seu default — nunca redeclaram o número 0.7 por conta própria."
    ),
)

# ---------------------------------------------------------------------------
# 7. Invariantes do próprio sistema — não são calibração
# ---------------------------------------------------------------------------

GRADE_SCALE_MIN = CalibrationParameter(
    name="GRADE_SCALE_MIN",
    value=Decimal("0.0"),
    unit="grade_points_0_10",
    definition="Limite inferior (inclusivo) da escala de notas do Sinaliza.",
    source="Constraint CHECK de `grades.value` da Epic 1 (migration 0003; docs/data-model.md)",
    source_refs=(),
    confidence=Confidence.HIGH,
    kind=ParameterKind.SYSTEM_INVARIANT,
    used_by_generator=True,
    rationale=(
        "Não é calibração: vem do schema do próprio sistema, não do INEP. "
        "Fica aqui para que o gerador nunca produza uma linha que a própria "
        "aplicação não poderia ter escrito."
    ),
)

GRADE_SCALE_MAX = CalibrationParameter(
    name="GRADE_SCALE_MAX",
    value=Decimal("10.0"),
    unit="grade_points_0_10",
    definition="Limite superior (inclusivo) da escala de notas do Sinaliza.",
    source="Constraint CHECK de `grades.value` da Epic 1 (migration 0003; docs/data-model.md)",
    source_refs=(),
    confidence=Confidence.HIGH,
    kind=ParameterKind.SYSTEM_INVARIANT,
    used_by_generator=True,
    rationale="Ver GRADE_SCALE_MIN.",
)


# ---------------------------------------------------------------------------
# Registro
#
# Derivado por introspecção do próprio namespace, de propósito: uma lista
# mantida à mão silenciosamente deixaria de fora um parâmetro novo, e os
# testes de proveniência passariam sem nunca tê-lo visto.
# ---------------------------------------------------------------------------


def _collect_parameters() -> tuple[CalibrationParameter, ...]:
    return tuple(
        sorted(
            (v for v in globals().values() if isinstance(v, CalibrationParameter)),
            key=lambda p: p.name,
        )
    )


ALL_PARAMETERS: tuple[CalibrationParameter, ...] = _collect_parameters()

PARAMETERS_BY_NAME: Mapping[str, CalibrationParameter] = MappingProxyType(
    {p.name: p for p in ALL_PARAMETERS}
)

#: Os parâmetros que o gerador realmente consome — referências públicas de
#: ordem de grandeza ficam de fora.
GENERATOR_PARAMETERS: tuple[CalibrationParameter, ...] = tuple(
    p for p in ALL_PARAMETERS if p.used_by_generator
)
