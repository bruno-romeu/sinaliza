"""Tests for `app.synthetic.calibration` (Story 2.4).

The point of this module is intellectual honesty about what is actually
calibrated against a Brazilian public base and what is not. Provenance
recorded only in comments cannot be tested, so the module exposes it as
data — and these tests assert over that data.

None of these tests touch the database: the module under test is pure
constants and metadata. `conftest.py`'s session fixtures are simply not
requested.
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from app.synthetic import calibration
from app.synthetic.calibration import (
    ALL_PARAMETERS,
    GENERATOR_PARAMETERS,
    PARAMETERS_BY_NAME,
    CalibrationParameter,
    Confidence,
    GradeBand,
    ParameterKind,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]

#: The three variables `research.md` found to have no Brazilian public source
#: at all, plus the 0–10 grade distribution, which exists only as a proxy.
#: All four must be flagged as design assumptions, never as calibrated data.
UNSOURCED_PARAMETER_NAMES = (
    "DAILY_ATTENDANCE_RATE_BASELINE",
    "DAILY_ATTENDANCE_RATE_AT_RISK_FLOOR",
    "ASSIGNMENT_NON_DELIVERY_RATE_BASELINE",
    "ASSIGNMENT_PARTIAL_DELIVERY_RATE_BASELINE",
    "ASSIGNMENT_NON_DELIVERY_RATE_AT_RISK_CEILING",
    "GRADE_DISTRIBUTION",
    "SYNTHETIC_PROFILE_PROPORTIONS",
)

#: Of those, the ones with no public anchor whatsoever — not even a proxy.
NO_ANCHOR_AT_ALL_NAMES = tuple(
    name for name in UNSOURCED_PARAMETER_NAMES if name != "GRADE_DISTRIBUTION"
)


def _numeric_leaves(value: object) -> list[float]:
    """Flatten a parameter value into its numeric leaves."""
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return [float(value)]
    if isinstance(value, GradeBand):
        return [float(value.min_value), float(value.max_value), float(value.share)]
    if isinstance(value, tuple):
        return [leaf for item in value for leaf in _numeric_leaves(item)]
    if hasattr(value, "items"):
        return [leaf for item in value.values() for leaf in _numeric_leaves(item)]
    raise AssertionError(f"unexpected value type in a calibration parameter: {type(value)!r}")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_matches_the_module_namespace() -> None:
    """A new constant cannot escape the provenance tests below.

    Re-derived here independently of `ALL_PARAMETERS` so a broken registry
    is caught too.
    """
    from_namespace = {
        name
        for name, value in vars(calibration).items()
        if isinstance(value, CalibrationParameter)
    }
    assert from_namespace, "no calibration parameters found in the module"
    assert {p.name for p in ALL_PARAMETERS} == from_namespace
    assert set(PARAMETERS_BY_NAME) == from_namespace
    assert len(ALL_PARAMETERS) == len(from_namespace), "duplicate parameter names"


def test_each_parameter_name_matches_its_module_attribute() -> None:
    for attribute_name, value in vars(calibration).items():
        if isinstance(value, CalibrationParameter):
            assert value.name == attribute_name


def test_generator_parameters_exclude_public_reference_only_entries() -> None:
    assert GENERATOR_PARAMETERS
    assert set(GENERATOR_PARAMETERS) <= set(ALL_PARAMETERS)
    for parameter in GENERATOR_PARAMETERS:
        assert parameter.used_by_generator is True
        assert parameter.kind is not ParameterKind.PUBLIC_REFERENCE


# ---------------------------------------------------------------------------
# Provenance — AC 1 and AC 3
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("parameter", ALL_PARAMETERS, ids=lambda p: p.name)
def test_every_parameter_carries_non_empty_provenance(parameter: CalibrationParameter) -> None:
    """AC 1: source and confidence, on every single exported parameter."""
    assert parameter.source.strip(), f"{parameter.name} has an empty source"
    assert isinstance(parameter.confidence, Confidence)
    assert isinstance(parameter.kind, ParameterKind)
    assert parameter.definition.strip(), f"{parameter.name} has an empty definition"
    assert parameter.rationale.strip(), f"{parameter.name} has an empty rationale"
    assert isinstance(parameter.used_by_generator, bool)


@pytest.mark.parametrize("name", UNSOURCED_PARAMETER_NAMES)
def test_parameters_without_a_brazilian_public_source_are_design_assumptions(name: str) -> None:
    """AC 3: never dressed up as calibrated data."""
    parameter = PARAMETERS_BY_NAME[name]
    assert parameter.kind is ParameterKind.DESIGN_ASSUMPTION
    assert parameter.is_design_assumption is True


@pytest.mark.parametrize("name", NO_ANCHOR_AT_ALL_NAMES)
def test_parameters_with_no_anchor_at_all_claim_no_confidence(name: str) -> None:
    """Daily attendance, assignment delivery and the profile mix.

    No Brazilian public base measures any of them, so there is nothing to
    have confidence in and no citation to give.
    """
    parameter = PARAMETERS_BY_NAME[name]
    assert parameter.confidence is Confidence.NONE
    assert parameter.source_refs == ()


def test_grade_distribution_is_a_documented_proxy_not_calibrated_data() -> None:
    grades = PARAMETERS_BY_NAME["GRADE_DISTRIBUTION"]
    assert grades.kind is ParameterKind.DESIGN_ASSUMPTION
    assert grades.confidence is Confidence.MEDIUM
    assert grades.source_refs, "the SAEB proxy anchor must be cited"

    anchor = PARAMETERS_BY_NAME["SAEB_INSUFFICIENT_SHARE_MATH_FINAL_YEAR"]
    assert anchor.kind is ParameterKind.PUBLIC_REFERENCE
    assert anchor.used_by_generator is False
    insufficient = next(band for band in grades.value if band.label == "Insuficiente")
    assert insufficient.share == anchor.value, "only the anchored share may come from SAEB"


@pytest.mark.parametrize(
    "parameter",
    [p for p in ALL_PARAMETERS if p.kind is ParameterKind.CALIBRATED],
    ids=lambda p: p.name,
)
def test_calibrated_parameters_cite_a_source_and_claim_real_confidence(
    parameter: CalibrationParameter,
) -> None:
    assert parameter.source_refs, f"{parameter.name} claims calibration without a citation"
    assert parameter.confidence in (Confidence.HIGH, Confidence.MEDIUM)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("ABANDONMENT_RATE_EF", 0.030),
        ("EVASION_RATE_EM", 0.059),
        ("FAILURE_RATE_EM", 0.039),
        ("COMBINED_FAILURE_RATE_EM_FIRST_YEAR", (0.164, 0.213)),
        ("SAEB_INSUFFICIENT_SHARE_MATH_FINAL_YEAR", 0.59),
        ("PNAD_ADJUSTED_NET_ATTENDANCE_RATE_EF", (0.989, 1.000)),
        ("PNAD_ADJUSTED_NET_ATTENDANCE_RATE_EM", 0.806),
    ],
)
def test_sourced_values_match_the_published_statistics(name: str, expected: object) -> None:
    """Pins every number that claims a citation.

    A silent edit here would leave the source text pointing at a statistic
    the value no longer reports.
    """
    assert PARAMETERS_BY_NAME[name].value == pytest.approx(expected)


@pytest.mark.parametrize(
    "parameter",
    [p for p in ALL_PARAMETERS if p.kind is ParameterKind.PUBLIC_REFERENCE],
    ids=lambda p: p.name,
)
def test_public_reference_parameters_never_feed_the_generator(
    parameter: CalibrationParameter,
) -> None:
    """PNAD measures access to school, SAEB measures proficiency.

    Neither is the variable the generator needs, so neither may be used as
    a generation parameter.
    """
    assert parameter.used_by_generator is False
    assert parameter.source_refs


def test_pnad_attendance_is_recorded_but_is_not_the_attendance_parameter() -> None:
    attendance = PARAMETERS_BY_NAME["DAILY_ATTENDANCE_RATE_BASELINE"]
    pnad_ef = PARAMETERS_BY_NAME["PNAD_ADJUSTED_NET_ATTENDANCE_RATE_EF"]
    pnad_em = PARAMETERS_BY_NAME["PNAD_ADJUSTED_NET_ATTENDANCE_RATE_EM"]

    assert attendance.used_by_generator is True
    assert pnad_ef.used_by_generator is False
    assert pnad_em.used_by_generator is False
    assert attendance.value not in _numeric_leaves(pnad_ef.value)
    assert attendance.value != pnad_em.value


# ---------------------------------------------------------------------------
# Abandonment and evasion are two variables, never one
# ---------------------------------------------------------------------------


def test_abandonment_and_evasion_are_distinct_parameters() -> None:
    abandonment = PARAMETERS_BY_NAME["ABANDONMENT_RATE_EF"]
    evasion = PARAMETERS_BY_NAME["EVASION_RATE_EM"]

    assert abandonment is not evasion
    assert abandonment.value != evasion.value
    assert abandonment.definition != evasion.definition
    assert "ABANDONO" in abandonment.definition
    assert "EVASÃO" in evasion.definition
    # The INEP distinction must be stated, not merely implied by the names.
    assert "abandono" in evasion.definition.lower()


def test_abandonment_and_evasion_are_never_summed_into_a_parameter() -> None:
    abandonment = PARAMETERS_BY_NAME["ABANDONMENT_RATE_EF"].value
    evasion = PARAMETERS_BY_NAME["EVASION_RATE_EM"].value
    forbidden_sum = abandonment + evasion

    for parameter in ALL_PARAMETERS:
        for leaf in _numeric_leaves(parameter.value):
            assert leaf != pytest.approx(forbidden_sum), (
                f"{parameter.name} appears to be abandono + evasão — the two are "
                "different INEP metrics and must never be summed"
            )


def test_failure_rate_is_a_third_distinct_metric() -> None:
    values = {
        PARAMETERS_BY_NAME["ABANDONMENT_RATE_EF"].value,
        PARAMETERS_BY_NAME["EVASION_RATE_EM"].value,
        PARAMETERS_BY_NAME["FAILURE_RATE_EM"].value,
    }
    assert len(values) == 3


def test_first_year_em_is_flagged_as_the_elevated_risk_subgroup() -> None:
    cohort = PARAMETERS_BY_NAME["COMBINED_FAILURE_RATE_EM_FIRST_YEAR"]
    low, high = cohort.value
    assert 0.0 <= low < high <= 1.0
    assert low > PARAMETERS_BY_NAME["EVASION_RATE_EM"].value
    # It combines reprovação + abandono as its source publishes it — the
    # definition has to say so, so nobody reads it as abandono + evasão.
    assert "reprovação" in cohort.definition.lower()


# ---------------------------------------------------------------------------
# Sane bounds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "parameter",
    [p for p in ALL_PARAMETERS if p.unit == "proportion"],
    ids=lambda p: p.name,
)
def test_proportions_stay_within_the_unit_interval(parameter: CalibrationParameter) -> None:
    leaves = _numeric_leaves(parameter.value)
    assert leaves
    for leaf in leaves:
        assert 0.0 <= leaf <= 1.0, f"{parameter.name} carries {leaf}, outside [0, 1]"


@pytest.mark.parametrize(
    "parameter",
    [p for p in ALL_PARAMETERS if p.unit == "grade_points_0_10"],
    ids=lambda p: p.name,
)
def test_grade_points_stay_within_the_epic_1_scale(parameter: CalibrationParameter) -> None:
    for leaf in _numeric_leaves(parameter.value):
        assert 0.0 <= leaf <= 10.0


def test_grade_scale_bounds_match_the_epic_1_check_constraint() -> None:
    assert PARAMETERS_BY_NAME["GRADE_SCALE_MIN"].value == Decimal("0.0")
    assert PARAMETERS_BY_NAME["GRADE_SCALE_MAX"].value == Decimal("10.0")
    assert PARAMETERS_BY_NAME["GRADE_SCALE_MIN"].kind is ParameterKind.SYSTEM_INVARIANT
    assert PARAMETERS_BY_NAME["GRADE_SCALE_MAX"].kind is ParameterKind.SYSTEM_INVARIANT


def test_grade_distribution_partitions_the_scale_without_gaps_or_overlap() -> None:
    bands = PARAMETERS_BY_NAME["GRADE_DISTRIBUTION"].value
    assert len(bands) == 4
    assert sum(band.share for band in bands) == pytest.approx(1.0)

    scale_min = PARAMETERS_BY_NAME["GRADE_SCALE_MIN"].value
    scale_max = PARAMETERS_BY_NAME["GRADE_SCALE_MAX"].value
    assert bands[0].min_value == scale_min
    assert bands[-1].max_value == scale_max

    for band in bands:
        assert 0.0 < band.share <= 1.0
        assert scale_min <= band.min_value <= band.max_value <= scale_max
    for lower, upper in zip(bands, bands[1:]):
        assert lower.max_value < upper.min_value, "grade bands must not overlap"


def test_profile_proportions_sum_to_one_and_cover_the_required_spectrum() -> None:
    proportions = PARAMETERS_BY_NAME["SYNTHETIC_PROFILE_PROPORTIONS"].value
    assert sum(proportions.values()) == pytest.approx(1.0)
    # epic-2-context.md: the set must bracket the spectrum RF-11 has to tell
    # apart — at least one stable and one combined-deterioration profile.
    assert "STABLE" in proportions
    assert "COMBINED_DETERIORATION" in proportions
    for share in proportions.values():
        assert 0.0 < share < 1.0


def test_baseline_assignment_shares_leave_room_for_delivered() -> None:
    non_delivery = PARAMETERS_BY_NAME["ASSIGNMENT_NON_DELIVERY_RATE_BASELINE"].value
    partial = PARAMETERS_BY_NAME["ASSIGNMENT_PARTIAL_DELIVERY_RATE_BASELINE"].value
    assert non_delivery + partial < 1.0


def test_at_risk_bounds_are_worse_than_the_stable_baseline() -> None:
    assert (
        PARAMETERS_BY_NAME["DAILY_ATTENDANCE_RATE_AT_RISK_FLOOR"].value
        < PARAMETERS_BY_NAME["DAILY_ATTENDANCE_RATE_BASELINE"].value
    )
    assert (
        PARAMETERS_BY_NAME["ASSIGNMENT_NON_DELIVERY_RATE_AT_RISK_CEILING"].value
        > PARAMETERS_BY_NAME["ASSIGNMENT_NON_DELIVERY_RATE_BASELINE"].value
    )


# ---------------------------------------------------------------------------
# Immutability and absence of real data
# ---------------------------------------------------------------------------


def test_parameters_are_frozen() -> None:
    parameter = ALL_PARAMETERS[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        parameter.value = 0.1  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        PARAMETERS_BY_NAME["GRADE_DISTRIBUTION"].value[0].share = 0.1  # type: ignore[misc]
    assert isinstance(ALL_PARAMETERS, tuple)
    with pytest.raises(TypeError):
        PARAMETERS_BY_NAME["extra"] = parameter  # type: ignore[index]


@pytest.mark.parametrize("parameter", ALL_PARAMETERS, ids=lambda p: p.name)
def test_no_parameter_carries_person_level_data(parameter: CalibrationParameter) -> None:
    """AC 4 / RNF-07: aggregate rates only, never a student-level datum.

    Since Censo Escolar 2021 INEP publishes school-aggregated microdata, so
    there is nothing per-student to leak in the first place — this asserts
    the module stayed that way.
    """
    leaves = _numeric_leaves(parameter.value)
    assert leaves, f"{parameter.name} has no numeric content"
    if isinstance(parameter.value, tuple) and parameter.value:
        for item in parameter.value:
            if isinstance(item, GradeBand):
                assert item.label in {
                    "Insuficiente",
                    "Básico",
                    "Proficiente",
                    "Avançado",
                }


# ---------------------------------------------------------------------------
# AC 2 — offline only: no network, no database, importable with nothing running
# ---------------------------------------------------------------------------


_IMPORT_PROBE = r"""
import sys
import socket


def _blocked(*args, **kwargs):
    raise AssertionError("network access attempted during import")


socket.socket = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked

import app.synthetic.calibration as calibration

forbidden = (
    "sqlalchemy",
    "psycopg",
    "psycopg2",
    "asyncpg",
    "alembic",
    "httpx",
    "requests",
    "urllib.request",
    "http.client",
    "fastapi",
    "starlette",
    "app.main",
    "app.config",
    "app.composition",
    "app.infrastructure",
    "app.presentation",
    "app.synthetic.generate",
)
loaded = sorted(
    name
    for name in sys.modules
    if any(name == f or name.startswith(f + ".") for f in forbidden)
)
assert not loaded, "forbidden modules imported: %r" % (loaded,)
assert calibration.ALL_PARAMETERS, "registry is empty"
print("IMPORT_PROBE_OK")
"""


def test_module_imports_offline_with_no_database_and_no_sockets() -> None:
    """AC 2: the public base is consulted offline, at calibration time only.

    Runs in a clean subprocess with every database/JWT environment variable
    removed and `socket` sabotaged, so a network call or an ORM/driver import
    sneaking in would fail loudly instead of passing unnoticed.
    """
    env = {k: v for k, v in os.environ.items()}
    for key in ("DATABASE_URL", "TEST_DATABASE_URL", "JWT_SECRET"):
        env.pop(key, None)
    env["PYTHONPATH"] = str(BACKEND_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [sys.executable, "-c", _IMPORT_PROBE],
        cwd=str(BACKEND_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )

    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "IMPORT_PROBE_OK" in result.stdout


def test_module_does_not_import_story_2_1_or_infrastructure_modules() -> None:
    """The calibration module is an input to the generator, not a consumer."""
    source = (BACKEND_ROOT / "app" / "synthetic" / "calibration.py").read_text(encoding="utf-8")
    import_lines = [
        line.strip() for line in source.splitlines() if line.startswith(("import ", "from "))
    ]
    assert import_lines, "no import statements found — is the file being read correctly?"
    joined = " ".join(import_lines)
    for forbidden in (
        "app.synthetic.generate",
        "app.infrastructure",
        "app.presentation",
        "app.application",
        "sqlalchemy",
        "psycopg",
        "fastapi",
        "httpx",
        "requests",
        "urllib",
        "socket",
    ):
        assert forbidden not in joined, f"calibration.py must not import {forbidden}"


def test_synthetic_package_init_is_byte_empty() -> None:
    """Story 2.1 creates the same file on a sibling branch.

    Byte-identical empty on both sides is what lets the two branches merge
    without a conflict.
    """
    init_path = BACKEND_ROOT / "app" / "synthetic" / "__init__.py"
    assert init_path.read_bytes() == b""
