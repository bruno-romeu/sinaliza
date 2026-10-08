"""Deterministic pedagogical-observation text per `SyntheticProfile` (Story
2.5).

Pure module: zero I/O, zero SQLAlchemy imports (AD-2's spirit, `profiles.py`/
`facts.py`'s precedent). Every observation's id and selected template are
derived from `(seed, student_id, period)` via `app.synthetic.rng` — never
ambient randomness or wall-clock time — so the same seed reproduces a
byte-identical base (RNF-13). `created_at` is derived from the period alone
(`period.end_date` at noon UTC): every observation in the same period shares
one timestamp, regardless of seed or student.

Every template below is a plain literal string, never an f-string that
embeds a fabricated statistic: no invented absence counts, no percentages,
no judgment-label vocabulary ("risco", "evasão", "abandono", "alerta") —
`EXPERIENCE.md`'s Voice and Tone. `STABLE` only ever selects from
`_ROUTINE_TEMPLATES`. `FALLING_ATTENDANCE` only from
`_ATTENDANCE_DECLINE_TEMPLATES`. `FALLING_GRADES` only from
`_PERFORMANCE_DECLINE_TEMPLATES`. `COMBINED_DETERIORATION` composes one
attendance-decline fragment with one assignment-decline fragment (mirrors
`EXPERIENCE.md`'s own Do example: "queda de frequência e aumento de
atividades pendentes") — the composition itself never introduces a number,
only joins two already-literal fragments with fixed connective text.

Decline templates intensify by trend stage (`early`/`mid`/`late`, computed
from `period_index/total_periods` exactly like `profiles.py::_progress`) but
stay descriptive, never a diagnosis or prediction.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Literal

from app.domain.student import SyntheticProfile
from app.synthetic.facts import PeriodWindow
from app.synthetic.population import GeneratedPopulation
from app.synthetic.rng import derived_key, stable_uuid

Stage = Literal["early", "mid", "late"]

#: Routine/no-trend templates — `STABLE`'s only source (spec Boundaries &
#: Constraints). Plain fixed sentences, no fabricated numbers.
_ROUTINE_TEMPLATES: tuple[str, ...] = (
    "Participação habitual nas atividades em sala neste período.",
    "Frequência dentro da faixa habitual neste período.",
    "Entregas de atividades dentro do esperado neste período.",
    "Comportamento e participação sem alterações notáveis neste período.",
    "Envolvimento nas discussões em sala consistente com períodos anteriores.",
)

#: Attendance-decline templates — `FALLING_ATTENDANCE`'s only source,
#: keyed by trend stage (intensifies early -> late, stays descriptive).
_ATTENDANCE_DECLINE_TEMPLATES: dict[Stage, tuple[str, ...]] = {
    "early": (
        "Frequência levemente reduzida neste período em relação ao período anterior.",
        "Algumas faltas a mais que o habitual neste período.",
    ),
    "mid": (
        "Frequência reduzida neste período, com mais faltas que no período anterior.",
        "Queda de frequência perceptível ao longo deste período.",
    ),
    "late": (
        "Frequência bastante reduzida neste período.",
        "Faltas frequentes ao longo deste período, bem acima do padrão anterior.",
    ),
}

#: Performance-decline templates — `FALLING_GRADES`'s only source, keyed by
#: trend stage. Describes the grade trend without restating a numeric value
#: (the grade itself is already a first-class fact column).
_PERFORMANCE_DECLINE_TEMPLATES: dict[Stage, tuple[str, ...]] = {
    "early": (
        "Desempenho nas avaliações levemente abaixo do observado em períodos anteriores.",
        "Notas um pouco abaixo do padrão anterior neste período.",
    ),
    "mid": (
        "Desempenho nas avaliações abaixo do padrão anterior neste período.",
        "Resultados nas avaliações em queda ao longo deste período.",
    ),
    "late": (
        "Desempenho nas avaliações significativamente abaixo do padrão anterior neste período.",
        "Notas consistentemente baixas ao longo deste período, bem abaixo do padrão anterior.",
    ),
}

#: `COMBINED_DETERIORATION` composition fragments — attendance half,
#: keyed by trend stage. Joined with `_COMBINED_ASSIGNMENT_FRAGMENTS` and
#: `_COMBINED_PREFIX` (Design Notes: "composes two sentences instead of
#: three" — attendance + assignments only, never grades, to avoid drifting
#: into evaluative language).
_COMBINED_ATTENDANCE_FRAGMENTS: dict[Stage, tuple[str, ...]] = {
    "early": ("frequência levemente reduzida", "algumas faltas a mais que o habitual"),
    "mid": ("queda de frequência", "frequência reduzida ao longo deste período"),
    "late": ("queda acentuada de frequência", "faltas frequentes ao longo deste período"),
}

#: `COMBINED_DETERIORATION` composition fragments — assignment half.
_COMBINED_ASSIGNMENT_FRAGMENTS: dict[Stage, tuple[str, ...]] = {
    "early": (
        "aumento pontual de atividades pendentes",
        "algumas atividades não entregues a mais que o habitual",
    ),
    "mid": (
        "aumento de atividades pendentes",
        "mais atividades não entregues que no período anterior",
    ),
    "late": (
        "aumento acentuado de atividades pendentes",
        "diversas atividades não entregues ao longo deste período",
    ),
}

#: Fixed connective text joining the two `COMBINED_DETERIORATION` fragments
#: (mirrors `EXPERIENCE.md`'s "queda de frequência e aumento de atividades
#: pendentes" worked example). Never an f-string carrying a number.
_COMBINED_PREFIX = "Mudança observada neste período: "


@dataclass(frozen=True)
class GeneratedObservation:
    id: uuid.UUID
    student_id: uuid.UUID
    author_user_id: uuid.UUID
    text: str
    created_at: datetime


def _progress(index: int, total: int) -> float:
    """`index / (total - 1)`, or `1.0` when `total <= 1` — mirrors
    `profiles.py::_progress` exactly (same division-by-zero handling), so a
    deteriorating profile's observation text reaches `late` in the same
    period its numeric facts reach their worst state."""
    if total <= 1:
        return 1.0
    return index / (total - 1)


def _stage(progress: float) -> Stage:
    """Maps a `[0, 1]` progress fraction onto one of three trend stages."""
    if progress < 1 / 3:
        return "early"
    if progress < 2 / 3:
        return "mid"
    return "late"


def _pick(options: tuple[str, ...], seed: int, *labels: str) -> str:
    """A deterministic pick from `options`, addressed by
    `(seed, "observation", *labels)` — same construction `profiles.py` uses
    for its own template/value selection."""
    index = derived_key(seed, "observation", *labels) % len(options)
    return options[index]


def _text_for(
    seed: int,
    student_id: uuid.UUID,
    period_label: str,
    profile: SyntheticProfile,
    stage: Stage,
) -> str:
    """The observation text for `student_id` in the period addressed by
    `period_label`, drawn exclusively from `profile`'s own template set."""
    if profile is SyntheticProfile.STABLE:
        return _pick(_ROUTINE_TEMPLATES, seed, str(student_id), period_label, "routine")

    if profile is SyntheticProfile.FALLING_ATTENDANCE:
        return _pick(
            _ATTENDANCE_DECLINE_TEMPLATES[stage],
            seed,
            str(student_id),
            period_label,
            "attendance_decline",
            stage,
        )

    if profile is SyntheticProfile.FALLING_GRADES:
        return _pick(
            _PERFORMANCE_DECLINE_TEMPLATES[stage],
            seed,
            str(student_id),
            period_label,
            "performance_decline",
            stage,
        )

    # SyntheticProfile.COMBINED_DETERIORATION — the only remaining member
    # (SyntheticProfile has exactly 4 values, asserted by Story 2.2's own
    # parity test).
    attendance_fragment = _pick(
        _COMBINED_ATTENDANCE_FRAGMENTS[stage],
        seed,
        str(student_id),
        period_label,
        "combined_attendance",
        stage,
    )
    assignment_fragment = _pick(
        _COMBINED_ASSIGNMENT_FRAGMENTS[stage],
        seed,
        str(student_id),
        period_label,
        "combined_assignment",
        stage,
    )
    return f"{_COMBINED_PREFIX}{attendance_fragment} e {assignment_fragment}."


def build_observations(
    population: GeneratedPopulation,
    periods: tuple[PeriodWindow, ...],
    author_user_id: uuid.UUID,
    seed: int,
) -> tuple[GeneratedObservation, ...]:
    """Deterministically builds one `GeneratedObservation` per `(student,
    period)` — the same granularity `facts.py` uses for grades/assignments,
    so a deteriorating student's observation text visibly tracks the same
    period-indexed trend their numeric facts already show (Design Notes)."""
    total_periods = len(periods)
    observations: list[GeneratedObservation] = []

    for student in population.students:
        profile = student.synthetic_profile
        for period_index, period in enumerate(periods):
            stage = _stage(_progress(period_index, total_periods))
            text = _text_for(seed, student.id, period.id_label, profile, stage)
            observations.append(
                GeneratedObservation(
                    id=stable_uuid(seed, "observation", str(student.id), period.id_label),
                    student_id=student.id,
                    author_user_id=author_user_id,
                    text=text,
                    created_at=datetime.combine(period.end_date, time(12, 0), tzinfo=UTC),
                )
            )

    return tuple(observations)
