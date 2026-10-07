"""Covers every row of the spec's CLI-invocation matrix plus the Acceptance
Criteria list. Always runs the generator at reduced volume (<=~24 students,
spec AC) — the full ~200-student base is never exercised in CI, only timed
manually (see spec Implementation Notes / Verification).

Uses `db_session` directly with no seeded fixtures (spec Code Map: "no new
fixture needed; the new tests use `db_session` and deliberately request no
seeded fixtures") — a clean schema inside the test's own rolled-back
transaction is exactly what "clean database" scenarios need.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.domain.student import DatasetSplit, SyntheticProfile
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    ClassroomModel,
    EnrollmentModel,
    StudentModel,
    SyntheticGenerationRunModel,
)
from app.synthetic.fingerprint import population_fingerprint
from app.synthetic.generate import (
    GENERATOR_VERSION,
    DatabasePopulatedError,
    _build_arg_parser,
    is_populated,
    run_generation,
)
from app.synthetic.population import GenerationConfig, _classroom_sizes, build_population

# Reduced-volume config shared by most tests: 3 classrooms of 4, exact 50/50
# split so the global TRAIN share is checkable without rounding noise.
_REDUCED_CONFIG = GenerationConfig(
    seed=42, student_count=12, students_per_classroom=4, train_ratio=0.5
)


def _seed_academic_periods(db_session: Session, academic_year: int = 2026) -> None:
    """A small local helper (not a `conftest.py` fixture — spec Code Map) so
    every test that calls `run_generation` has a school calendar to build
    facts from. Two bimesters are enough for these generation-shape tests;
    `test_synthetic_facts_generation.py` owns exercising fact volume/content."""
    db_session.add_all(
        [
            AcademicPeriodModel(
                label="1º Bimestre",
                start_date=date(academic_year, 2, 2),
                end_date=date(academic_year, 4, 17),
                order_index=1,
            ),
            AcademicPeriodModel(
                label="2º Bimestre",
                start_date=date(academic_year, 4, 20),
                end_date=date(academic_year, 6, 26),
                order_index=2,
            ),
        ]
    )
    db_session.commit()


def _no_real_data_pattern() -> re.Pattern[str]:
    # Digits, '@', or anything CPF/phone-shaped (runs of digits with optional
    # separators) — RNF-07.
    return re.compile(r"[0-9@]")


def test_first_run_clean_database_creates_expected_rows(db_session: Session) -> None:
    _seed_academic_periods(db_session)
    fingerprint, run = run_generation(db_session, _REDUCED_CONFIG, reset=False)

    classrooms = db_session.query(ClassroomModel).all()
    students = db_session.query(StudentModel).all()
    enrollments = db_session.query(EnrollmentModel).all()
    runs = db_session.query(SyntheticGenerationRunModel).all()

    assert len(classrooms) == 3
    assert len(students) == 12
    assert len(enrollments) == 12
    assert len(runs) == 1

    assert run.seed == 42
    assert run.generator_version == GENERATOR_VERSION
    assert run.student_count == 12
    assert run.train_ratio == Decimal("0.5")
    assert run.executed_at is not None

    assert all(s.synthetic_profile in set(SyntheticProfile) for s in students)
    assert isinstance(fingerprint, str) and len(fingerprint) == 64  # sha256 hex digest


def test_same_seed_twice_produces_byte_identical_fingerprint(db_session: Session) -> None:
    _seed_academic_periods(db_session)
    fingerprint_1, _ = run_generation(db_session, _REDUCED_CONFIG, reset=False)
    fingerprint_2, _ = run_generation(db_session, _REDUCED_CONFIG, reset=True)

    assert fingerprint_1 == fingerprint_2
    # Determinism proven by content hash, never by row count (RNF-13) — but
    # confirm row counts didn't silently double either.
    assert db_session.query(StudentModel).count() == 12
    # A second run row is written, not a replacement of the first.
    assert db_session.query(SyntheticGenerationRunModel).count() == 2


def test_different_seed_produces_different_fingerprint(db_session: Session) -> None:
    _seed_academic_periods(db_session)
    fingerprint_42, _ = run_generation(db_session, _REDUCED_CONFIG, reset=False)

    other_config = GenerationConfig(
        seed=43, student_count=12, students_per_classroom=4, train_ratio=0.5
    )
    fingerprint_43, _ = run_generation(db_session, other_config, reset=True)

    assert fingerprint_42 != fingerprint_43


def test_populated_database_without_reset_raises_and_writes_nothing(db_session: Session) -> None:
    _seed_academic_periods(db_session)
    run_generation(db_session, _REDUCED_CONFIG, reset=False)
    student_count_before = db_session.query(StudentModel).count()
    run_count_before = db_session.query(SyntheticGenerationRunModel).count()

    with pytest.raises(DatabasePopulatedError, match="--reset"):
        run_generation(db_session, _REDUCED_CONFIG, reset=False)

    assert db_session.query(StudentModel).count() == student_count_before
    assert db_session.query(SyntheticGenerationRunModel).count() == run_count_before


def test_populated_database_with_reset_regenerates(db_session: Session) -> None:
    _seed_academic_periods(db_session)
    run_generation(db_session, _REDUCED_CONFIG, reset=False)

    other_config = GenerationConfig(
        seed=99, student_count=12, students_per_classroom=4, train_ratio=0.5
    )
    _, run = run_generation(db_session, other_config, reset=True)

    assert run.seed == 99
    assert db_session.query(StudentModel).count() == 12
    assert db_session.query(SyntheticGenerationRunModel).count() == 2


def test_reduced_volume_matches_requested_counts(db_session: Session) -> None:
    _seed_academic_periods(db_session)
    config = GenerationConfig(seed=7, student_count=12, students_per_classroom=4)
    _, run = run_generation(db_session, config, reset=False)

    assert db_session.query(ClassroomModel).count() == 3
    assert db_session.query(StudentModel).count() == 12
    assert db_session.query(EnrollmentModel).count() == 12
    assert run.student_count == 12


def test_invalid_arguments_rejected_by_argparse_before_touching_db() -> None:
    parser = _build_arg_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--seed", "42", "--train-ratio", "1.0"])
    assert exc_info.value.code == 2

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--seed", "42", "--students", "0"])
    assert exc_info.value.code == 2

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--seed", "-1"])
    assert exc_info.value.code == 2

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--seed", "42", "--academic-year", "0"])
    assert exc_info.value.code == 2


def test_every_student_has_dataset_split_and_every_classroom_has_both(
    db_session: Session,
) -> None:
    _seed_academic_periods(db_session)
    run_generation(db_session, _REDUCED_CONFIG, reset=False)

    students = db_session.query(StudentModel).all()
    assert all(s.dataset_split in (DatasetSplit.TRAIN, DatasetSplit.EVAL_DEMO) for s in students)

    global_counts = Counter(s.dataset_split for s in students)
    assert global_counts[DatasetSplit.TRAIN] > 0
    assert global_counts[DatasetSplit.EVAL_DEMO] > 0
    # Exact 50/50 config: global TRAIN share matches train_ratio exactly.
    assert global_counts[DatasetSplit.TRAIN] / len(students) == 0.5

    for classroom in db_session.query(ClassroomModel).all():
        classroom_student_ids = {
            e.student_id
            for e in db_session.query(EnrollmentModel)
            .filter(EnrollmentModel.classroom_id == classroom.id)
            .all()
        }
        classroom_splits = {
            s.dataset_split for s in students if s.id in classroom_student_ids
        }
        assert DatasetSplit.TRAIN in classroom_splits
        assert DatasetSplit.EVAL_DEMO in classroom_splits


def test_no_real_data_in_generated_text_fields(db_session: Session) -> None:
    _seed_academic_periods(db_session)
    run_generation(db_session, _REDUCED_CONFIG, reset=False)
    pattern = _no_real_data_pattern()

    for student in db_session.query(StudentModel).all():
        assert not pattern.search(student.name), student.name
        parts = student.name.split(" ")
        assert len(parts) == 3, student.name  # given + first surname + second surname

    for classroom in db_session.query(ClassroomModel).all():
        assert not pattern.search(classroom.name), classroom.name


def test_pure_population_construction_has_no_io_dependency() -> None:
    # population.py must never need a database — build directly, no fixture.
    population = build_population(_REDUCED_CONFIG)
    assert len(population.classrooms) == 3
    assert len(population.students) == 12
    assert len(population.enrollments) == 12

    # Deterministic: same config, same output, called twice with no DB at all.
    assert build_population(_REDUCED_CONFIG) == population


def test_is_populated_false_on_clean_database(db_session: Session) -> None:
    assert is_populated(db_session) is False


def test_fingerprint_function_used_directly_matches_generation_return_value(
    db_session: Session,
) -> None:
    _seed_academic_periods(db_session)
    fingerprint, _ = run_generation(db_session, _REDUCED_CONFIG, reset=False)
    assert population_fingerprint(db_session) == fingerprint


def test_global_train_share_matches_ratio_at_real_default_config() -> None:
    # The actual default CLI config (200 students / 25 per classroom /
    # train_ratio=0.7): per-classroom `round(25 * 0.7)` == 18 everywhere due
    # to banker's rounding, which would otherwise drift the global ratio to
    # 0.72. The remainder-carrying split must land on exactly 0.7.
    config = GenerationConfig(seed=1, student_count=200, students_per_classroom=25, train_ratio=0.7)
    population = build_population(config)

    train_count = sum(
        1 for s in population.students if s.dataset_split == DatasetSplit.TRAIN
    )
    assert train_count / len(population.students) == 0.7


def test_classroom_sizes_never_below_two_students() -> None:
    # 201 students / 25 per classroom leaves a remainder classroom of
    # exactly 1 student, which can never contain both TRAIN and EVAL_DEMO.
    sizes = _classroom_sizes(201, 25)
    assert sum(sizes) == 201
    assert all(size >= 2 for size in sizes)


def test_students_per_classroom_of_one_rejected() -> None:
    # students_per_classroom=1 makes every classroom size 1 by construction
    # (no trailing-remainder folding applies), so it can never satisfy "every
    # classroom contains both TRAIN and EVAL_DEMO" — reject up front.
    with pytest.raises(ValueError, match="students_per_classroom"):
        GenerationConfig(seed=1, student_count=4, students_per_classroom=1)


def test_small_classroom_extreme_ratio_still_has_both_splits() -> None:
    # student_count=2, students_per_classroom=2, train_ratio=0.1: the raw
    # cumulative-remainder calculation gives train_count=0 for this
    # classroom. Every classroom must still have both splits.
    config = GenerationConfig(
        seed=1, student_count=2, students_per_classroom=2, train_ratio=0.1
    )
    population = build_population(config)

    splits = {s.dataset_split for s in population.students}
    assert DatasetSplit.TRAIN in splits
    assert DatasetSplit.EVAL_DEMO in splits


def test_openapi_export_never_contains_synthetic_profile(tmp_path) -> None:
    from app import export_openapi as export_openapi_module

    output_path = tmp_path / "openapi.json"
    original_output_path = export_openapi_module.OUTPUT_PATH
    export_openapi_module.OUTPUT_PATH = output_path
    try:
        export_openapi_module.export_openapi()
        content = output_path.read_text(encoding="utf-8")
    finally:
        export_openapi_module.OUTPUT_PATH = original_output_path

    assert "synthetic_profile" not in content
