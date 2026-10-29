"""Tests for Story 2.3 — split de dataset em TRAIN/EVAL_DEMO.

Story 2.3 is "majoritariamente verificação" (epic-2-plan.md, Onda 3): the
split assignment itself shipped in Story 2.1 (`population.py`) and AD-11's
read-side enforcement shipped in Epic 1 (`repositories/base.py`, already
regression-tested per-fixture in `test_attendance.py`/`test_assignments.py`/
`test_grades.py`/`test_observations.py`). What this file adds:

1. The split ratio is a named, documented constant
   (`calibration.TRAIN_EVAL_SPLIT_RATIO`), not a magic number duplicated in
   `population.py`/`generate.py`.
2. Exactly two `dataset_split` values ever exist on a generated base — never
   a third category.
3. `EVAL_DEMO` students get a complete trajectory (every school day, every
   period, every assignment) across the full synthetic school year — never a
   truncated one.
4. An end-to-end regression, driven by a real generated population (not a
   single hand-built fixture), proving the `EVAL_DEMO`-only read filter
   (AD-11) holds for every classroom and every generated `TRAIN` student,
   not just the one example each existing per-service test constructs.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.domain.student import DatasetSplit
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    AssignmentSubmissionModel,
    AttendanceRecordModel,
    ClassroomModel,
    EnrollmentModel,
    GradeModel,
    StudentModel,
)
from app.infrastructure.repositories.sqlalchemy_student_repository import (
    SqlAlchemyStudentRepository,
)
from app.synthetic import calibration
from app.synthetic.facts import SUBJECTS, PeriodWindow, build_facts, school_days
from app.synthetic.generate import _build_arg_parser, run_generation
from app.synthetic.population import GenerationConfig, build_population
from tests.test_synthetic_facts_generation import _seed_coordination_user

# A full synthetic school year (4 bimesters), mirroring
# `test_synthetic_facts_generation.py`'s shape, so "complete trajectory
# across the full school year" is checked against a realistic calendar, not
# a 2-period stub.
_PERIODS: list[tuple[str, date, date, int]] = [
    ("1º Bimestre", date(2026, 2, 2), date(2026, 4, 17), 1),
    ("2º Bimestre", date(2026, 4, 20), date(2026, 6, 26), 2),
    ("3º Bimestre", date(2026, 7, 27), date(2026, 9, 25), 3),
    ("4º Bimestre", date(2026, 9, 28), date(2026, 12, 18), 4),
]

# Reduced volume (epic DoD: never the full ~200-student base in CI), with an
# uneven split ratio so TRAIN and EVAL_DEMO are never accidentally equal-sized
# in a way that would mask an asymmetric bug.
_CONFIG = GenerationConfig(seed=11, student_count=24, students_per_classroom=8, train_ratio=0.625)


def _seed_periods(db_session: Session) -> None:
    db_session.add_all(
        [
            AcademicPeriodModel(label=label, start_date=start, end_date=end, order_index=order)
            for label, start, end, order in _PERIODS
        ]
    )
    db_session.commit()


def _period_windows() -> tuple[PeriodWindow, ...]:
    return tuple(
        PeriodWindow(id_label=f"period-{order}", start_date=start, end_date=end, order_index=order)
        for _, start, end, order in sorted(_PERIODS, key=lambda row: row[3])
    )


# ---------------------------------------------------------------------------
# AC: the split ratio is a named, documented constant
# ---------------------------------------------------------------------------


def test_train_eval_split_ratio_is_a_named_documented_calibration_parameter() -> None:
    parameter = calibration.TRAIN_EVAL_SPLIT_RATIO
    assert parameter.name == "TRAIN_EVAL_SPLIT_RATIO"
    assert parameter.unit == "proportion"
    assert 0.0 < parameter.value < 1.0
    assert parameter.used_by_generator is True
    # No Brazilian public base measures an ML train/eval split proportion —
    # this must be flagged as a design assumption, never dressed up as
    # calibrated data (AC 3 of the epic's calibration-honesty constraint).
    assert parameter.kind is calibration.ParameterKind.DESIGN_ASSUMPTION
    assert parameter.confidence is calibration.Confidence.NONE
    assert parameter.source.strip()
    assert parameter.definition.strip()
    assert parameter.rationale.strip()
    # Swept by calibration.py's own introspection-based registry — a new
    # constant cannot silently skip the provenance tests in
    # test_synthetic_calibration.py.
    assert parameter in calibration.ALL_PARAMETERS
    assert parameter in calibration.GENERATOR_PARAMETERS


def test_generation_config_default_train_ratio_is_the_named_constant_not_a_duplicate_literal() -> None:
    default_config = GenerationConfig(seed=0)
    assert default_config.train_ratio == calibration.TRAIN_EVAL_SPLIT_RATIO.value


def test_cli_default_train_ratio_is_the_named_constant_not_a_duplicate_literal() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(["--seed", "0"])
    assert args.train_ratio == calibration.TRAIN_EVAL_SPLIT_RATIO.value


# ---------------------------------------------------------------------------
# AC: exactly two dataset_split values exist — never a third category
# ---------------------------------------------------------------------------


def test_exactly_two_dataset_split_values_exist_on_a_generated_base(db_session: Session) -> None:
    _seed_periods(db_session)
    _seed_coordination_user(db_session)
    run_generation(db_session, _CONFIG, reset=False)

    observed_splits = {s.dataset_split for s in db_session.query(StudentModel).all()}
    assert observed_splits == {DatasetSplit.TRAIN, DatasetSplit.EVAL_DEMO}

    # Structural guarantee, not just an empirical one for this run: the enum
    # itself only ever has these two members, so a third category is not
    # merely absent here — it is unrepresentable.
    assert set(DatasetSplit) == {DatasetSplit.TRAIN, DatasetSplit.EVAL_DEMO}


# ---------------------------------------------------------------------------
# AC: EVAL_DEMO gets a complete trajectory across the full school year
# ---------------------------------------------------------------------------


def test_eval_demo_students_have_complete_trajectory_across_the_full_school_year() -> None:
    population = build_population(_CONFIG)
    periods = _period_windows()
    facts = build_facts(population, periods, _CONFIG)

    total_days = len(school_days(periods))
    eval_demo_ids = {
        s.id for s in population.students if s.dataset_split == DatasetSplit.EVAL_DEMO
    }
    train_ids = {s.id for s in population.students if s.dataset_split == DatasetSplit.TRAIN}
    assert eval_demo_ids and train_ids, "both splits must be present in this config"

    attendance_by_student: dict = {}
    for record in facts.attendance_records:
        attendance_by_student.setdefault(record.student_id, []).append(record)

    grades_by_student: dict = {}
    for grade in facts.grades:
        grades_by_student.setdefault(grade.student_id, []).append(grade)

    submissions_by_student: dict = {}
    for submission in facts.assignment_submissions:
        submissions_by_student.setdefault(submission.student_id, []).append(submission)

    # Every EVAL_DEMO student has one attendance record per school day
    # (never truncated to a partial year) and one grade per (period,
    # subject) — the full-year, known-outcome trajectory RF-23 needs.
    for student_id in eval_demo_ids:
        assert len(attendance_by_student[student_id]) == total_days
        assert len(grades_by_student[student_id]) == len(periods) * len(SUBJECTS)
        # Submission count depends on classroom assignment volume, which is
        # identical for every student in the same classroom — asserted below
        # by comparing against a TRAIN student in the same classroom.

    # EVAL_DEMO's completeness is not special-cased relative to TRAIN: the
    # generator assigns facts uniformly over `population.students` and only
    # the split label differs (facts.py never branches on dataset_split).
    # This is the structural reason Epic 5's TRAIN/EVAL_DEMO partition can
    # never silently give EVAL_DEMO a shorter or different trajectory.
    for student_id in train_ids:
        assert len(attendance_by_student[student_id]) == total_days
        assert len(grades_by_student[student_id]) == len(periods) * len(SUBJECTS)

    classroom_by_student = {
        e.student_id: e.classroom_id for e in population.enrollments
    }
    submissions_per_classroom: dict = {}
    for student_id, submissions in submissions_by_student.items():
        submissions_per_classroom.setdefault(classroom_by_student[student_id], set()).add(
            len(submissions)
        )
    # Within each classroom, every student (TRAIN or EVAL_DEMO alike) submits
    # to the exact same number of assignments — no split-dependent gap.
    for classroom_id, counts in submissions_per_classroom.items():
        assert len(counts) == 1, (
            f"classroom {classroom_id} has students with differing submission "
            "counts across the dataset split"
        )


# ---------------------------------------------------------------------------
# AC: TRAIN never appears in any application-facing read — end-to-end,
# driven by a real generated population rather than one hand-built fixture
# per service (that per-service coverage already exists in
# test_attendance.py/test_assignments.py/test_grades.py/test_observations.py)
# ---------------------------------------------------------------------------


def test_generated_train_students_never_appear_in_list_enrolled_for_any_classroom(
    db_session: Session,
) -> None:
    _seed_periods(db_session)
    _seed_coordination_user(db_session)
    run_generation(db_session, _CONFIG, reset=False)

    repository = SqlAlchemyStudentRepository(db_session)
    classrooms = db_session.query(ClassroomModel).all()
    assert classrooms

    for classroom in classrooms:
        enrolled = repository.list_enrolled(classroom.id)
        assert enrolled, "every generated classroom must have EVAL_DEMO students enrolled"
        assert all(student.dataset_split == DatasetSplit.EVAL_DEMO for student in enrolled)


def test_generated_train_students_fail_exists_enrollment_for_their_real_classroom(
    db_session: Session,
) -> None:
    _seed_periods(db_session)
    _seed_coordination_user(db_session)
    run_generation(db_session, _CONFIG, reset=False)

    repository = SqlAlchemyStudentRepository(db_session)
    train_enrollments = (
        db_session.query(EnrollmentModel)
        .join(StudentModel, StudentModel.id == EnrollmentModel.student_id)
        .filter(StudentModel.dataset_split == DatasetSplit.TRAIN)
        .all()
    )
    assert train_enrollments, "this config must generate at least one TRAIN enrollment"

    for enrollment in train_enrollments:
        assert repository.exists_enrollment(enrollment.student_id, enrollment.classroom_id) is False


def test_generated_train_facts_exist_in_the_database_but_never_via_the_student_repository(
    db_session: Session,
) -> None:
    """TRAIN rows are written (Epic 5 needs them to train offline) but are
    unreachable through the one read path the web application uses to
    resolve a student — confirming AD-4/AD-11 is a read-side filter, not an
    accidental absence of TRAIN data altogether."""
    _seed_periods(db_session)
    _seed_coordination_user(db_session)
    run_generation(db_session, _CONFIG, reset=False)

    train_student = (
        db_session.query(StudentModel).filter(StudentModel.dataset_split == DatasetSplit.TRAIN).first()
    )
    assert train_student is not None

    # TRAIN facts were in fact generated and persisted...
    assert (
        db_session.query(AttendanceRecordModel)
        .filter(AttendanceRecordModel.student_id == train_student.id)
        .count()
        > 0
    )
    assert (
        db_session.query(GradeModel).filter(GradeModel.student_id == train_student.id).count() > 0
    )
    assert (
        db_session.query(AssignmentSubmissionModel)
        .filter(AssignmentSubmissionModel.student_id == train_student.id)
        .count()
        > 0
    )

    # ...but the student repository, the only path application services use
    # to resolve a student, never surfaces this id.
    repository = SqlAlchemyStudentRepository(db_session)
    enrollment = (
        db_session.query(EnrollmentModel)
        .filter(EnrollmentModel.student_id == train_student.id)
        .one()
    )
    assert repository.exists_enrollment(train_student.id, enrollment.classroom_id) is False
    enrolled = repository.list_enrolled(enrollment.classroom_id)
    assert train_student.id not in {s.id for s in enrolled}
