"""Testes unitários das funções puras de feature temporal
(spec-features-temporais-de-trajetoria, CAP-2).

Sem banco e sem fixture: são funções sobre sequências. O foco é o
comportamento com **histórico curto ou vazio**, que é onde uma feature
temporal erra se errar — e onde um `0.0` no lugar de `None` passaria
despercebido afirmando "não houve mudança" para quem não tem dado.
"""

from __future__ import annotations

import pytest

from app.ml.temporal_features import (
    first_to_last_group_delta,
    half_split_delta,
    longest_true_run,
)


def test_pipeline_keeps_a_column_that_is_entirely_missing_at_fit_time() -> None:
    """Regressão de um defeito que as features temporais tornaram alcançável.

    `SimpleImputer(strategy="mean")` **descarta** silenciosamente uma coluna
    sem nenhum valor observado no ajuste. O pipeline passaria a ter menos
    colunas do que `FEATURE_COLUMNS` declara, e a inferência — que monta a
    matriz completa por `feature_vector()` — quebraria, ou casaria colunas
    trocadas se o número coincidisse.

    `require_matching_feature_schema()` não alcança este caso: o esquema de
    features *confere*; foi o ajuste que encolheu. Com os quatro agregados
    antigos era quase impossível uma coluna inteira ser `None` (qualquer
    estudante com um fato já a preenchia); com `grade_delta`, que exige dois
    períodos, um conjunto pequeno cai nisso com facilidade."""
    from app.ml.feature_aggregation import FEATURE_COLUMNS
    from app.ml.pipeline import build_pipeline

    width = len(FEATURE_COLUMNS)
    # Última coluna inteiramente ausente no ajuste.
    feature_matrix = [
        [0.9] * (width - 1) + [None],
        [0.1] * (width - 1) + [None],
    ]
    pipeline = build_pipeline()
    pipeline.fit(feature_matrix, ["STABLE", "FALLING_ATTENDANCE"])

    # Uma linha de inferência com a coluna preenchida precisa caber: se o
    # ajuste tivesse descartado a coluna, isto levantaria ValueError.
    assert len(pipeline.predict([[0.5] * width])) == 1


class TestHalfSplitDelta:
    def test_empty_history_has_no_defined_delta(self) -> None:
        assert half_split_delta([]) is None

    def test_single_point_history_has_no_defined_delta(self) -> None:
        """Um ponto só não tem variação definida. `0.0` afirmaria
        estabilidade onde há ausência de observação."""
        assert half_split_delta([1.0]) is None

    def test_flat_history_yields_zero(self) -> None:
        """Aqui `0.0` é a resposta certa: há dado, e ele não mudou."""
        assert half_split_delta([1.0, 1.0, 1.0, 1.0]) == 0.0

    def test_falling_history_is_negative(self) -> None:
        assert half_split_delta([1.0, 1.0, 0.0, 0.0]) == -1.0

    def test_rising_history_is_positive(self) -> None:
        assert half_split_delta([0.0, 0.0, 1.0, 1.0]) == 1.0

    def test_two_points_split_one_and_one(self) -> None:
        assert half_split_delta([1.0, 0.0]) == -1.0

    def test_odd_length_puts_the_middle_point_in_the_second_half(self) -> None:
        """Convenção declarada: com 3 pontos, `[0]` contra `[1, 2]`.
        Arbitrária, mas estável — o teste existe para que ela não mude sem
        alguém perceber."""
        assert half_split_delta([1.0, 0.0, 0.0]) == -1.0
        assert half_split_delta([0.0, 1.0, 1.0]) == 1.0

    def test_is_proportional_to_the_slope_of_a_linear_ramp(self) -> None:
        """A rampa do gerador é linear; o delta entre metades precisa
        ordenar rampas por inclinação para servir de feature."""
        gentle = [1.0 - 0.1 * index for index in range(10)]
        steep = [1.0 - 0.2 * index for index in range(10)]
        gentle_delta = half_split_delta(gentle)
        steep_delta = half_split_delta(steep)
        assert gentle_delta is not None and steep_delta is not None
        assert steep_delta < gentle_delta < 0


class TestLongestTrueRun:
    def test_empty_history_is_zero(self) -> None:
        """Contagem, não taxa: "nenhuma falta" é valor real, mesma convenção
        de `observation_count`."""
        assert longest_true_run([]) == 0

    def test_no_true_is_zero(self) -> None:
        assert longest_true_run([False, False, False]) == 0

    def test_all_true_is_the_full_length(self) -> None:
        assert longest_true_run([True, True, True]) == 3

    def test_takes_the_longest_run_not_the_last(self) -> None:
        assert longest_true_run([True, True, True, False, True]) == 3

    def test_takes_the_longest_run_not_the_first(self) -> None:
        assert longest_true_run([True, False, True, True, True]) == 3

    def test_counts_grouping_not_total(self) -> None:
        """A diferença em relação a uma taxa de faltas: as duas sequências
        têm o mesmo número de faltas e corridas diferentes. É isso que a
        feature acrescenta a `attendance_trend`."""
        spread = [True, False, True, False, True, False]
        clustered = [True, True, True, False, False, False]
        assert sum(spread) == sum(clustered)
        assert longest_true_run(spread) == 1
        assert longest_true_run(clustered) == 3


class TestFirstToLastGroupDelta:
    def test_no_groups_has_no_defined_delta(self) -> None:
        assert first_to_last_group_delta({}) is None

    def test_single_group_has_no_defined_delta(self) -> None:
        """Um estudante com notas em um único período não tem delta."""
        assert first_to_last_group_delta({1: [7.0, 8.0]}) is None

    def test_empty_groups_do_not_count_as_groups(self) -> None:
        """Um período sem nenhuma nota não é um período com média zero."""
        assert first_to_last_group_delta({1: [7.0], 2: []}) is None

    def test_falling_grades_across_periods_is_negative(self) -> None:
        assert first_to_last_group_delta({1: [8.0], 2: [6.0], 3: [2.0]}) == -6.0

    def test_orders_by_group_key_not_insertion_order(self) -> None:
        """Os grupos são períodos ordenados por `order_index`. A ordem em que
        o SQL devolveu as linhas não pode inverter o sinal da feature."""
        assert first_to_last_group_delta({3: [2.0], 1: [8.0], 2: [6.0]}) == -6.0

    def test_uses_the_mean_within_each_group(self) -> None:
        assert first_to_last_group_delta({1: [8.0, 6.0], 2: [5.0, 3.0]}) == -3.0

    def test_ignores_intermediate_groups(self) -> None:
        """Primeiro contra último, por construção: a rampa do gerador é
        monotônica, e incluir o meio só adicionaria ruído de variação
        per-período."""
        assert first_to_last_group_delta({1: [8.0], 2: [0.0], 3: [6.0]}) == pytest.approx(-2.0)
