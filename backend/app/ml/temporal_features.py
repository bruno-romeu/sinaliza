"""Funções puras de feature temporal (spec-features-temporais-de-trajetoria).

Zero I/O, zero SQLAlchemy: recebem sequências já ordenadas e devolvem números.
O SQL que as alimenta vive em `feature_aggregation.py`. A separação é o que
torna estas funções testáveis sem banco — e o comportamento com histórico
curto, que é onde elas erram se errarem, é exatamente o que precisa de teste
unitário barato.

**Por que features temporais existem.** Lendo `app/synthetic/profiles.py`,
todo perfil não-`STABLE` é definido por uma *rampa no tempo*: a probabilidade
diária de presença interpola do baseline até um piso ao longo dos dias letivos;
o quantil de nota é multiplicado por `(1 - progress)` ao longo dos períodos; a
taxa de não-entrega interpola do baseline até um teto. Uma média anual sobre
uma rampa linear devolve aproximadamente o ponto médio dela — preserva o nível,
apaga a inclinação, que é justamente a grandeza que **define** o perfil. Estas
funções devolvem a inclinação.

**Ausência.** Delta sem pontos suficientes é `None`, nunca `0.0`. `0.0`
afirmaria "não houve mudança"; o que houve foi ausência de dado, e o
`SimpleImputer` do pipeline sabe lidar com a diferença. Contagem é `0`, pela
mesma convenção que já rege `observation_count` — "nenhuma falta" é um valor
real.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def half_split_delta(values: Sequence[float]) -> float | None:
    """Média da segunda metade menos média da primeira metade de uma série
    cronológica. Negativo = caindo.

    Diferença entre metades, e não coeficiente de uma regressão linear, porque
    a rampa do gerador é linear: a diferença entre metades é proporcional à
    inclinação e separa os perfis igual, com uma implementação que se explica
    numa frase. Um `polyfit` de grau 1 daria essencialmente a mesma ordenação
    com mais maquinário entre o dado e o leitor.

    Com número ímpar de pontos o ponto do meio cai na segunda metade — com 3
    pontos, `[0]` contra `[1, 2]`. Qualquer escolha é arbitrária; esta é
    declarada e estável.

    `None` com menos de dois pontos: uma série de um ponto só não tem
    variação definida, e devolver `0.0` ali afirmaria estabilidade onde há
    ausência de observação."""
    if len(values) < 2:
        return None
    midpoint = len(values) // 2
    first_half = values[:midpoint]
    second_half = values[midpoint:]
    return (sum(second_half) / len(second_half)) - (sum(first_half) / len(first_half))


def longest_true_run(flags: Sequence[bool]) -> int:
    """O maior número de `True` consecutivos. `0` para sequência vazia.

    Usada para faltas consecutivas (`AGENTS.md` §Features a nomeia). Ela
    acrescenta algo a `attendance_trend` sem ser redundante: a maior corrida
    de faltas depende de como as faltas se **agrupam**, não só de quantas
    existem. Com a probabilidade diária de presença caindo até o piso, as
    corridas no fim do ano se alongam de forma não-linear, enquanto a
    diferença entre metades cresce linearmente — são leituras diferentes da
    mesma rampa."""
    longest = 0
    current = 0
    for flag in flags:
        if flag:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def first_to_last_group_delta(values_by_group: Mapping[int, Sequence[float]]) -> float | None:
    """Média do último grupo menos média do primeiro, ordenando os grupos pela
    chave. Negativo = caindo.

    Para notas os grupos são períodos letivos, ordenados por
    `AcademicPeriod.order_index` — nunca pela data do lançamento. A rampa de
    nota do gerador é indexada por período (`_progress(period_index,
    total_periods)`), então comparar o primeiro período com notas contra o
    último período com notas é a leitura que corresponde à regra geradora. Uma
    nota lançada com atraso move a data sem mover o período a que pertence.

    `None` com menos de dois grupos: um estudante com notas em um único período
    não tem delta definido. Grupos vazios são ignorados — um período sem
    nenhuma nota não é um período com média zero."""
    non_empty = {key: values for key, values in values_by_group.items() if values}
    if len(non_empty) < 2:
        return None
    ordered_keys = sorted(non_empty)
    first = non_empty[ordered_keys[0]]
    last = non_empty[ordered_keys[-1]]
    return (sum(last) / len(last)) - (sum(first) / len(first))
