"""Pure unit tests for `app.synthetic.profiles` and `app.synthetic.facts` —
no database, no SQLAlchemy, no `conftest.py` fixtures (spec Code Map).

Also owns the enum/calibration parity test required by the spec's
Acceptance Criteria: `set(SyntheticProfile)` must equal
`set(calibration.SYNTHETIC_PROFILE_PROPORTIONS.value.keys())` exactly.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date
from decimal import Decimal

import pytest

from app.domain.assignment_submission import AssignmentSubmissionStatus
from app.domain.attendance import AttendanceStatus
from app.domain.student import DatasetSplit, SyntheticProfile
from app.synthetic import facts, profiles
from app.synthetic.calibration import (
    ASSIGNMENT_NON_DELIVERY_RATE_AT_RISK_CEILING,
    ASSIGNMENT_NON_DELIVERY_RATE_BASELINE,
    DAILY_ATTENDANCE_RATE_BASELINE,
    GRADE_SCALE_MAX,
    GRADE_SCALE_MIN,
    SYNTHETIC_PROFILE_PROPORTIONS,
)
from app.synthetic.facts import GeneratedFacts, PeriodWindow
from app.synthetic.population import (
    GeneratedClassroom,
    GeneratedEnrollment,
    GeneratedPopulation,
    GeneratedStudent,
    GenerationConfig,
)

SEED = 12345


def _student_ids(count: int) -> list[uuid.UUID]:
    # Deterministic, not `uuid.uuid4()`: statistical assertions below sample
    # over these ids, and a fresh random draw on every test run would make
    # pass/fail a coin flip near the tolerance boundary instead of a stable,
    # reproducible result.
    return [uuid.UUID(int=i) for i in range(count)]


# ---------------------------------------------------------------------------
# Enum/calibration parity (AC: RNF-13)
# ---------------------------------------------------------------------------


def test_syntheticprofile_enum_matches_calibration_proportion_keys_exactly() -> None:
    enum_values = {member.value for member in SyntheticProfile}
    calibration_keys = set(SYNTHETIC_PROFILE_PROPORTIONS.value.keys())
    assert enum_values == calibration_keys
    assert len(enum_values) == 4


# ---------------------------------------------------------------------------
# assign_profile
# ---------------------------------------------------------------------------


def test_assign_profile_is_deterministic() -> None:
    student_id = uuid.uuid4()
    assert profiles.assign_profile(SEED, student_id) == profiles.assign_profile(SEED, student_id)


def test_assign_profile_always_returns_a_valid_member() -> None:
    for student_id in _student_ids(500):
        assert profiles.assign_profile(SEED, student_id) in set(SyntheticProfile)


def test_assign_profile_different_seeds_differ_in_aggregate() -> None:
    ids = _student_ids(200)
    assignments_a = [profiles.assign_profile(1, sid) for sid in ids]
    assignments_b = [profiles.assign_profile(2, sid) for sid in ids]
    assert assignments_a != assignments_b


def test_assign_profile_distribution_matches_calibration_proportions() -> None:
    ids = _student_ids(8000)
    counts = Counter(profiles.assign_profile(SEED, sid) for sid in ids)
    proportions = SYNTHETIC_PROFILE_PROPORTIONS.value

    for key, expected_share in proportions.items():
        observed_share = counts[SyntheticProfile(key)] / len(ids)
        assert observed_share == pytest.approx(expected_share, abs=0.03)


# ---------------------------------------------------------------------------
# attendance_is_present
# ---------------------------------------------------------------------------


def test_attendance_is_present_stable_profile_has_no_day_trend() -> None:
    student_id = uuid.uuid4()
    total_days = 200
    first_quarter = sum(
        profiles.attendance_is_present(SEED, student_id, SyntheticProfile.STABLE, day, total_days)
        for day in range(0, total_days // 4)
    )
    last_quarter = sum(
        profiles.attendance_is_present(SEED, student_id, SyntheticProfile.STABLE, day, total_days)
        for day in range(total_days - total_days // 4, total_days)
    )
    quarter_size = total_days // 4
    first_rate = first_quarter / quarter_size
    last_rate = last_quarter / quarter_size
    assert abs(first_rate - last_rate) < 0.25  # both hover near the same baseline


def test_attendance_is_present_falling_attendance_declines_over_the_year() -> None:
    total_days = 200
    quarter_size = total_days // 4
    # Aggregate over many students for a statistically stable comparison.
    student_ids = _student_ids(100)

    first_quarter_presences = sum(
        profiles.attendance_is_present(
            SEED, sid, SyntheticProfile.FALLING_ATTENDANCE, day, total_days
        )
        for sid in student_ids
        for day in range(0, quarter_size)
    )
    last_quarter_presences = sum(
        profiles.attendance_is_present(
            SEED, sid, SyntheticProfile.FALLING_ATTENDANCE, day, total_days
        )
        for sid in student_ids
        for day in range(total_days - quarter_size, total_days)
    )

    first_rate = first_quarter_presences / (len(student_ids) * quarter_size)
    last_rate = last_quarter_presences / (len(student_ids) * quarter_size)

    assert first_rate > last_rate
    # Near the documented baseline/floor (0.95 -> 0.60).
    assert first_rate > 0.85
    assert last_rate < 0.75


def test_attendance_is_present_combined_deterioration_also_declines() -> None:
    total_days = 200
    quarter_size = total_days // 4
    student_ids = _student_ids(100)

    first_rate = sum(
        profiles.attendance_is_present(
            SEED, sid, SyntheticProfile.COMBINED_DETERIORATION, day, total_days
        )
        for sid in student_ids
        for day in range(0, quarter_size)
    ) / (len(student_ids) * quarter_size)
    last_rate = sum(
        profiles.attendance_is_present(
            SEED, sid, SyntheticProfile.COMBINED_DETERIORATION, day, total_days
        )
        for sid in student_ids
        for day in range(total_days - quarter_size, total_days)
    ) / (len(student_ids) * quarter_size)

    assert first_rate > last_rate


def test_attendance_is_present_falling_grades_profile_unaffected() -> None:
    # FALLING_GRADES must not touch attendance — rate stays at the baseline
    # regardless of day index.
    total_days = 200
    student_ids = _student_ids(200)
    first_day_rate = sum(
        profiles.attendance_is_present(SEED, sid, SyntheticProfile.FALLING_GRADES, 0, total_days)
        for sid in student_ids
    ) / len(student_ids)
    last_day_rate = sum(
        profiles.attendance_is_present(
            SEED, sid, SyntheticProfile.FALLING_GRADES, total_days - 1, total_days
        )
        for sid in student_ids
    ) / len(student_ids)
    baseline = DAILY_ATTENDANCE_RATE_BASELINE.value
    assert abs(first_day_rate - baseline) < 0.08
    assert abs(last_day_rate - baseline) < 0.08


def test_attendance_is_present_reproducible_with_same_seed() -> None:
    student_id = uuid.uuid4()
    sequence_1 = [
        profiles.attendance_is_present(SEED, student_id, SyntheticProfile.FALLING_ATTENDANCE, d, 100)
        for d in range(100)
    ]
    sequence_2 = [
        profiles.attendance_is_present(SEED, student_id, SyntheticProfile.FALLING_ATTENDANCE, d, 100)
        for d in range(100)
    ]
    assert sequence_1 == sequence_2


# ---------------------------------------------------------------------------
# grade_value
# ---------------------------------------------------------------------------


def test_grade_value_always_within_scale() -> None:
    for sid in _student_ids(50):
        for period_index in range(4):
            for profile in SyntheticProfile:
                value = profiles.grade_value(
                    SEED, sid, f"period-{period_index}", "Matemática", profile, period_index, 4
                )
                assert GRADE_SCALE_MIN.value <= value <= GRADE_SCALE_MAX.value
                assert isinstance(value, Decimal)


def test_grade_value_falling_grades_hits_exact_floor_at_final_period() -> None:
    # At the last period, progress == 1.0, so shifted = quantile * 0 == 0
    # exactly for every student — an exact, not merely statistical, claim.
    total_periods = 4
    last_period_index = total_periods - 1
    for sid in _student_ids(30):
        value = profiles.grade_value(
            SEED,
            sid,
            f"period-{last_period_index}",
            "Português",
            SyntheticProfile.FALLING_GRADES,
            last_period_index,
            total_periods,
        )
        assert value == Decimal("0.00")


def test_grade_value_combined_deterioration_hits_exact_floor_at_final_period() -> None:
    total_periods = 4
    last_period_index = total_periods - 1
    for sid in _student_ids(30):
        value = profiles.grade_value(
            SEED,
            sid,
            f"period-{last_period_index}",
            "Ciências",
            SyntheticProfile.COMBINED_DETERIORATION,
            last_period_index,
            total_periods,
        )
        assert value == Decimal("0.00")


def test_grade_value_stable_profile_unaffected_by_period_progress() -> None:
    # STABLE never shifts the quantile, so its mapped grade must match the
    # value obtained by passing progress-irrelevant indices (period_index=0,
    # total_periods=1 forces progress=1.0 internally but STABLE ignores it).
    sid = uuid.uuid4()
    value_mid_year = profiles.grade_value(SEED, sid, "period-2", "História", SyntheticProfile.STABLE, 2, 4)
    value_single_period = profiles.grade_value(
        SEED, sid, "period-2", "História", SyntheticProfile.STABLE, 0, 1
    )
    assert value_mid_year == value_single_period


def test_grade_value_reproducible_with_same_seed() -> None:
    sid = uuid.uuid4()
    first = profiles.grade_value(SEED, sid, "period-1", "Matemática", SyntheticProfile.STABLE, 1, 4)
    second = profiles.grade_value(SEED, sid, "period-1", "Matemática", SyntheticProfile.STABLE, 1, 4)
    assert first == second


# ---------------------------------------------------------------------------
# assignment_submission_status
# ---------------------------------------------------------------------------


def test_assignment_submission_status_returns_valid_member() -> None:
    for sid in _student_ids(50):
        status = profiles.assignment_submission_status(
            SEED, sid, "assignment-1", SyntheticProfile.STABLE, 0, 4
        )
        assert status in set(AssignmentSubmissionStatus)


def test_assignment_submission_status_combined_deterioration_worsens_over_periods() -> None:
    total_periods = 4
    student_ids = _student_ids(1000)

    first_period_not_delivered = sum(
        profiles.assignment_submission_status(
            SEED, sid, "assignment-x", SyntheticProfile.COMBINED_DETERIORATION, 0, total_periods
        )
        is AssignmentSubmissionStatus.NOT_DELIVERED
        for sid in student_ids
    ) / len(student_ids)

    last_period_not_delivered = sum(
        profiles.assignment_submission_status(
            SEED,
            sid,
            "assignment-x",
            SyntheticProfile.COMBINED_DETERIORATION,
            total_periods - 1,
            total_periods,
        )
        is AssignmentSubmissionStatus.NOT_DELIVERED
        for sid in student_ids
    ) / len(student_ids)

    assert last_period_not_delivered > first_period_not_delivered
    assert first_period_not_delivered == pytest.approx(
        ASSIGNMENT_NON_DELIVERY_RATE_BASELINE.value, abs=0.03
    )
    assert last_period_not_delivered == pytest.approx(
        ASSIGNMENT_NON_DELIVERY_RATE_AT_RISK_CEILING.value, abs=0.03
    )


def test_assignment_submission_status_other_profiles_unaffected_by_period() -> None:
    total_periods = 4
    student_ids = _student_ids(1000)

    for profile in (SyntheticProfile.STABLE, SyntheticProfile.FALLING_ATTENDANCE, SyntheticProfile.FALLING_GRADES):
        first_period_not_delivered = sum(
            profiles.assignment_submission_status(
                SEED, sid, "assignment-y", profile, 0, total_periods
            )
            is AssignmentSubmissionStatus.NOT_DELIVERED
            for sid in student_ids
        ) / len(student_ids)
        last_period_not_delivered = sum(
            profiles.assignment_submission_status(
                SEED, sid, "assignment-y", profile, total_periods - 1, total_periods
            )
            is AssignmentSubmissionStatus.NOT_DELIVERED
            for sid in student_ids
        ) / len(student_ids)
        assert abs(first_period_not_delivered - last_period_not_delivered) < 0.03


# ---------------------------------------------------------------------------
# facts.school_days
# ---------------------------------------------------------------------------


def test_school_days_excludes_weekends() -> None:
    period = PeriodWindow(
        id_label="period-1", start_date=date(2026, 2, 2), end_date=date(2026, 2, 8), order_index=1
    )  # Monday 2026-02-02 .. Sunday 2026-02-08
    days = facts.school_days((period,))
    assert all(day.weekday() < 5 for day in days)
    assert len(days) == 5


def test_school_days_excludes_gaps_between_periods() -> None:
    period_1 = PeriodWindow(
        id_label="period-1", start_date=date(2026, 2, 2), end_date=date(2026, 2, 6), order_index=1
    )
    period_2 = PeriodWindow(
        id_label="period-2", start_date=date(2026, 3, 2), end_date=date(2026, 3, 6), order_index=2
    )
    days = facts.school_days((period_1, period_2))
    assert date(2026, 2, 15) not in days  # inside the gap between periods
    assert len(days) == 10


def test_school_days_is_deterministic() -> None:
    period = PeriodWindow(
        id_label="period-1", start_date=date(2026, 2, 2), end_date=date(2026, 4, 17), order_index=1
    )
    assert facts.school_days((period,)) == facts.school_days((period,))


# ---------------------------------------------------------------------------
# facts._justification_is_justified — the 50/50 coin (Assumption 4)
# ---------------------------------------------------------------------------


def test_justification_is_justified_produces_both_outcomes() -> None:
    # Assumption 4's split has no calibration source and no AC distinguishing
    # the two statuses, but a coin that happened to always land the same way
    # would silently violate "50/50" without any test catching it.
    ids = _student_ids(500)
    outcomes = {facts._justification_is_justified(SEED, sid, date(2026, 3, 2)) for sid in ids}
    assert outcomes == {True, False}


# ---------------------------------------------------------------------------
# facts.build_facts — pure, no database
# ---------------------------------------------------------------------------


def _tiny_population() -> GeneratedPopulation:
    classroom = GeneratedClassroom(id=uuid.uuid4(), name="Turma Teste", academic_year=2026)
    students = [
        GeneratedStudent(
            id=uuid.uuid4(),
            name=f"Estudante {i}",
            dataset_split=DatasetSplit.EVAL_DEMO,
            synthetic_profile=profile,
        )
        for i, profile in enumerate(SyntheticProfile)
    ]
    enrollments = [
        GeneratedEnrollment(id=uuid.uuid4(), student_id=s.id, classroom_id=classroom.id)
        for s in students
    ]
    return GeneratedPopulation(
        classrooms=(classroom,), students=tuple(students), enrollments=tuple(enrollments)
    )


def _tiny_periods() -> tuple[PeriodWindow, ...]:
    return (
        PeriodWindow(
            id_label="period-1", start_date=date(2026, 2, 2), end_date=date(2026, 2, 6), order_index=1
        ),
        PeriodWindow(
            id_label="period-2", start_date=date(2026, 3, 2), end_date=date(2026, 3, 6), order_index=2
        ),
    )


def test_build_facts_has_no_io_dependency_and_is_deterministic() -> None:
    population = _tiny_population()
    periods = _tiny_periods()
    config = GenerationConfig(seed=SEED, student_count=len(population.students), students_per_classroom=4)

    result_1 = facts.build_facts(population, periods, config)
    result_2 = facts.build_facts(population, periods, config)

    assert result_1 == result_2
    assert isinstance(result_1, GeneratedFacts)


def test_build_facts_row_counts_match_expected_shape() -> None:
    population = _tiny_population()
    periods = _tiny_periods()
    config = GenerationConfig(seed=SEED, student_count=len(population.students), students_per_classroom=4)

    result = facts.build_facts(population, periods, config)

    school_day_count = len(facts.school_days(periods))
    student_count = len(population.students)
    subject_count = len(facts.SUBJECTS)
    period_count = len(periods)

    assert len(result.attendance_records) == student_count * school_day_count
    assert len(result.grades) == student_count * period_count * subject_count
    assert len(result.assignments) == len(population.classrooms) * period_count * subject_count
    assert len(result.assignment_submissions) == len(result.assignments) * student_count


def test_build_facts_attendance_records_are_unique_per_student_classroom_date() -> None:
    population = _tiny_population()
    periods = _tiny_periods()
    config = GenerationConfig(seed=SEED, student_count=len(population.students), students_per_classroom=4)

    result = facts.build_facts(population, periods, config)
    keys = [(r.student_id, r.classroom_id, r.date) for r in result.attendance_records]
    assert len(keys) == len(set(keys))


def test_build_facts_grade_values_within_scale() -> None:
    population = _tiny_population()
    periods = _tiny_periods()
    config = GenerationConfig(seed=SEED, student_count=len(population.students), students_per_classroom=4)

    result = facts.build_facts(population, periods, config)
    for grade in result.grades:
        assert GRADE_SCALE_MIN.value <= grade.value <= GRADE_SCALE_MAX.value


def test_build_facts_different_seed_changes_output() -> None:
    population = _tiny_population()
    periods = _tiny_periods()
    config_a = GenerationConfig(seed=1, student_count=len(population.students), students_per_classroom=4)
    config_b = GenerationConfig(seed=2, student_count=len(population.students), students_per_classroom=4)

    result_a = facts.build_facts(population, periods, config_a)
    result_b = facts.build_facts(population, periods, config_b)

    assert result_a != result_b
