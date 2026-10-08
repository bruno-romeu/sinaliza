"""DB-backed tests covering every row of the spec's CLI-invocation matrix
(spec I/O & Edge-Case Matrix) plus the Acceptance Criteria that need a real
Postgres database (attendance uniqueness, grade range — "proven by querying
the live Postgres after generation, not by code inspection alone").

Seeds its own `AcademicPeriodModel` rows directly (spec Code Map: "tests use
`db_session` with no pre-seeded fixtures" precedent) rather than depending on
`seed_dev_fixtures.py`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.attendance import AttendanceStatus
from app.domain.student import SyntheticProfile
from app.domain.user import UserRole
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    AssignmentModel,
    AssignmentSubmissionModel,
    AttendanceRecordModel,
    ClassroomModel,
    EnrollmentModel,
    GradeModel,
    StudentModel,
    SyntheticGenerationRunModel,
    UserModel,
)
from app.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher
from app.synthetic.facts import SUBJECTS, PeriodWindow, school_days
from app.synthetic.generate import MissingAcademicPeriodsError, run_generation
from app.synthetic.population import GenerationConfig

# A full synthetic school year (4 bimesters), shaped like
# `seed_dev_fixtures.py`'s — enough school days for "first quarter vs. last
# quarter" comparisons to be meaningful.
_PERIODS: list[tuple[str, date, date, int]] = [
    ("1º Bimestre", date(2026, 2, 2), date(2026, 4, 17), 1),
    ("2º Bimestre", date(2026, 4, 20), date(2026, 6, 26), 2),
    ("3º Bimestre", date(2026, 7, 27), date(2026, 9, 25), 3),
    ("4º Bimestre", date(2026, 9, 28), date(2026, 12, 18), 4),
]

# Reduced volume (spec Implementation Notes/epic DoD: "test suite exercises
# the generator at reduced volume, never the full base"), but large enough
# that every profile is realistically represented — empirically verified for
# seed=42 to produce at least one student of all 4 profiles.
_CONFIG = GenerationConfig(seed=42, student_count=48, students_per_classroom=12)


def _seed_periods(db_session: Session, periods: list[tuple[str, date, date, int]] = _PERIODS) -> None:
    db_session.add_all(
        [
            AcademicPeriodModel(label=label, start_date=start, end_date=end, order_index=order)
            for label, start, end, order in periods
        ]
    )
    db_session.commit()


def _seed_coordination_user(db_session: Session) -> None:
    """A small local helper (not a `conftest.py` fixture — spec Code Map,
    Spec Change Log), mirroring `_seed_periods`. `run_generation` now has a
    new precondition (Story 2.5: a resolvable `author_user_id`), so every
    test here that calls `run_generation` must also seed the coordination
    user it resolves via `get_settings().dev_seed_email`."""
    settings = get_settings()
    assert settings.dev_seed_email, (
        "DEV_SEED_EMAIL must be configured (via backend/.env) for this test suite to run"
    )
    email = settings.dev_seed_email.strip().lower()
    db_session.add(
        UserModel(
            name=settings.dev_seed_name,
            email=email,
            password_hash=BcryptPasswordHasher().hash("Senha-Correta-123"),
            role=UserRole.COORDENACAO_PEDAGOGICA,
        )
    )
    db_session.commit()


def _period_windows() -> tuple[PeriodWindow, ...]:
    return tuple(
        PeriodWindow(id_label=f"period-{order}", start_date=start, end_date=end, order_index=order)
        for _, start, end, order in sorted(_PERIODS, key=lambda row: row[3])
    )


def _total_school_days() -> int:
    return len(school_days(_period_windows()))


# ---------------------------------------------------------------------------
# Matrix row: clean DB, periods seeded
# ---------------------------------------------------------------------------


def test_clean_db_periods_seeded_populates_every_fact_table(db_session: Session) -> None:
    _seed_periods(db_session)
    _seed_coordination_user(db_session)
    fingerprint, run = run_generation(db_session, _CONFIG, reset=False)

    students = db_session.query(StudentModel).all()
    assert len(students) == _CONFIG.student_count
    assert all(s.synthetic_profile in set(SyntheticProfile) for s in students)

    classrooms = db_session.query(ClassroomModel).all()
    total_school_days = _total_school_days()

    attendance_count = db_session.query(AttendanceRecordModel).count()
    grade_count = db_session.query(GradeModel).count()
    assignment_count = db_session.query(AssignmentModel).count()
    submission_count = db_session.query(AssignmentSubmissionModel).count()

    assert attendance_count == len(students) * total_school_days
    assert grade_count == len(students) * len(_PERIODS) * len(SUBJECTS)
    assert assignment_count == len(classrooms) * len(_PERIODS) * len(SUBJECTS)
    # Every student submits to every assignment in their own classroom.
    students_per_classroom = len(students) // len(classrooms)
    assert submission_count == assignment_count * students_per_classroom

    assert isinstance(fingerprint, str) and len(fingerprint) == 64
    assert run.student_count == len(students)


# ---------------------------------------------------------------------------
# Matrix row: no periods seeded
# ---------------------------------------------------------------------------


def test_no_periods_seeded_writes_nothing_and_raises(db_session: Session) -> None:
    with pytest.raises(MissingAcademicPeriodsError, match="academic_periods"):
        run_generation(db_session, _CONFIG, reset=False)

    assert db_session.query(StudentModel).count() == 0
    assert db_session.query(ClassroomModel).count() == 0
    assert db_session.query(EnrollmentModel).count() == 0
    assert db_session.query(SyntheticGenerationRunModel).count() == 0
    assert db_session.query(AttendanceRecordModel).count() == 0
    assert db_session.query(GradeModel).count() == 0


def test_no_periods_seeded_error_names_academic_year(db_session: Session) -> None:
    with pytest.raises(MissingAcademicPeriodsError) as exc_info:
        run_generation(db_session, _CONFIG, reset=False)
    assert "academic_periods" in str(exc_info.value)
    assert "academic_year" in str(exc_info.value)


def test_periods_seeded_for_a_different_year_still_raises(db_session: Session) -> None:
    # config.academic_year defaults to 2026; periods seeded for 2027 must not
    # be treated as satisfying the requirement.
    _seed_periods(
        db_session,
        periods=[
            ("1º Bimestre 2027", date(2027, 2, 1), date(2027, 4, 15), 1),
        ],
    )
    with pytest.raises(MissingAcademicPeriodsError):
        run_generation(db_session, _CONFIG, reset=False)


def test_populated_db_with_reset_but_periods_missing_writes_nothing(db_session: Session) -> None:
    # Regression: the academic-period check must run *before*
    # `is_populated`/`reset_generated_data` wipe anything, so a populated
    # database + `--reset` + periods missing for the configured year still
    # writes nothing — the deletes must never start before the validation
    # that can abort the whole generation.
    _seed_periods(db_session)
    _seed_coordination_user(db_session)
    run_generation(db_session, _CONFIG, reset=False)

    student_count_before = db_session.query(StudentModel).count()
    classroom_count_before = db_session.query(ClassroomModel).count()
    attendance_count_before = db_session.query(AttendanceRecordModel).count()
    run_count_before = db_session.query(SyntheticGenerationRunModel).count()

    # Ask for a year with no matching periods, rather than mutating the
    # seeded `academic_periods` rows: the first run's `grades`/`assignments`
    # already hold foreign keys to those rows, so deleting them here would
    # fail on the same FK constraint the generator itself must never violate.
    mismatched_config = GenerationConfig(
        seed=_CONFIG.seed,
        student_count=_CONFIG.student_count,
        students_per_classroom=_CONFIG.students_per_classroom,
        academic_year=2099,
    )

    with pytest.raises(MissingAcademicPeriodsError):
        run_generation(db_session, mismatched_config, reset=True)

    # Nothing was wiped or regenerated: the pre-existing rows from the first
    # successful run are untouched.
    assert db_session.query(StudentModel).count() == student_count_before
    assert db_session.query(ClassroomModel).count() == classroom_count_before
    assert db_session.query(AttendanceRecordModel).count() == attendance_count_before
    assert db_session.query(SyntheticGenerationRunModel).count() == run_count_before


# ---------------------------------------------------------------------------
# Matrix row: same seed twice -> byte-identical fingerprint (now covering
# facts + profile, not just classrooms/students/enrollments)
# ---------------------------------------------------------------------------


def test_same_seed_twice_produces_byte_identical_fingerprint_covering_facts(
    db_session: Session,
) -> None:
    _seed_periods(db_session)
    _seed_coordination_user(db_session)
    fingerprint_1, _ = run_generation(db_session, _CONFIG, reset=False)
    fingerprint_2, _ = run_generation(db_session, _CONFIG, reset=True)

    assert fingerprint_1 == fingerprint_2
    assert db_session.query(AttendanceRecordModel).count() == _CONFIG.student_count * _total_school_days()


# ---------------------------------------------------------------------------
# Matrix row: different seed -> different fingerprint + different profile mix
# ---------------------------------------------------------------------------


def test_different_seed_produces_different_fingerprint_and_profile_mix(
    db_session: Session,
) -> None:
    _seed_periods(db_session)
    _seed_coordination_user(db_session)
    fingerprint_42, _ = run_generation(db_session, _CONFIG, reset=False)
    profiles_42 = Counter(s.synthetic_profile for s in db_session.query(StudentModel).all())

    other_config = GenerationConfig(seed=43, student_count=48, students_per_classroom=12)
    fingerprint_43, _ = run_generation(db_session, other_config, reset=True)
    profiles_43 = Counter(s.synthetic_profile for s in db_session.query(StudentModel).all())

    assert fingerprint_42 != fingerprint_43
    assert profiles_42 != profiles_43


# ---------------------------------------------------------------------------
# Matrix row: attendance uniqueness (DB UNIQUE never triggers)
# ---------------------------------------------------------------------------


def test_attendance_records_never_violate_uniqueness(db_session: Session) -> None:
    _seed_periods(db_session)
    _seed_coordination_user(db_session)
    run_generation(db_session, _CONFIG, reset=False)

    rows = db_session.query(
        AttendanceRecordModel.student_id, AttendanceRecordModel.classroom_id, AttendanceRecordModel.date
    ).all()
    keys = [(r[0], r[1], r[2]) for r in rows]
    assert len(keys) == len(set(keys))


# ---------------------------------------------------------------------------
# Matrix row: grade range (DB CHECK never triggers)
# ---------------------------------------------------------------------------


def test_grade_values_within_scale_in_live_postgres(db_session: Session) -> None:
    _seed_periods(db_session)
    _seed_coordination_user(db_session)
    run_generation(db_session, _CONFIG, reset=False)

    values = [row[0] for row in db_session.query(GradeModel.value).all()]
    assert values, "no grades were generated"
    for value in values:
        assert 0 <= value <= 10


# ---------------------------------------------------------------------------
# Matrix row: FALLING_ATTENDANCE student inspected
# ---------------------------------------------------------------------------


def test_falling_attendance_student_has_lower_presence_rate_later_in_the_year(
    db_session: Session,
) -> None:
    _seed_periods(db_session)
    _seed_coordination_user(db_session)
    run_generation(db_session, _CONFIG, reset=False)

    student = (
        db_session.query(StudentModel)
        .filter(StudentModel.synthetic_profile == SyntheticProfile.FALLING_ATTENDANCE)
        .first()
    )
    assert student is not None, "fixture seed/volume must produce at least one FALLING_ATTENDANCE student"

    records = (
        db_session.query(AttendanceRecordModel)
        .filter(AttendanceRecordModel.student_id == student.id)
        .order_by(AttendanceRecordModel.date)
        .all()
    )
    assert records

    quarter = len(records) // 4
    first_quarter = records[:quarter]
    last_quarter = records[-quarter:]

    def _presence_rate(rows):
        return sum(1 for r in rows if r.status == AttendanceStatus.PRESENT) / len(rows)

    first_rate = _presence_rate(first_quarter)
    last_rate = _presence_rate(last_quarter)
    assert last_rate < first_rate

    # Regenerating with the same seed reproduces the identical sequence of
    # statuses for this student.
    statuses_before = [r.status for r in records]
    run_generation(db_session, _CONFIG, reset=True)
    records_after = (
        db_session.query(AttendanceRecordModel)
        .filter(AttendanceRecordModel.student_id == student.id)
        .order_by(AttendanceRecordModel.date)
        .all()
    )
    statuses_after = [r.status for r in records_after]
    assert statuses_before == statuses_after


# ---------------------------------------------------------------------------
# Matrix row: COMBINED_DETERIORATION student inspected
# ---------------------------------------------------------------------------


def test_combined_deterioration_student_worsens_on_all_three_axes(db_session: Session) -> None:
    _seed_periods(db_session)
    _seed_coordination_user(db_session)
    run_generation(db_session, _CONFIG, reset=False)

    student = (
        db_session.query(StudentModel)
        .filter(StudentModel.synthetic_profile == SyntheticProfile.COMBINED_DETERIORATION)
        .first()
    )
    assert student is not None, "fixture seed/volume must produce at least one COMBINED_DETERIORATION student"

    # Attendance: last quarter of school days worse than the first.
    records = (
        db_session.query(AttendanceRecordModel)
        .filter(AttendanceRecordModel.student_id == student.id)
        .order_by(AttendanceRecordModel.date)
        .all()
    )
    quarter = len(records) // 4

    def _presence_rate(rows):
        return sum(1 for r in rows if r.status == AttendanceStatus.PRESENT) / len(rows)

    assert _presence_rate(records[-quarter:]) < _presence_rate(records[:quarter])

    # Grades: average value in the last period lower than in the first.
    grades = (
        db_session.query(GradeModel, AcademicPeriodModel.order_index)
        .join(AcademicPeriodModel, GradeModel.period_id == AcademicPeriodModel.id)
        .filter(GradeModel.student_id == student.id)
        .all()
    )
    by_period: dict[int, list] = defaultdict(list)
    for grade, order_index in grades:
        by_period[order_index].append(float(grade.value))

    first_order = min(by_period)
    last_order = max(by_period)
    first_avg = sum(by_period[first_order]) / len(by_period[first_order])
    last_avg = sum(by_period[last_order]) / len(by_period[last_order])
    assert last_avg < first_avg

    # Assignment non-delivery: higher share of NOT_DELIVERED in the last
    # period's assignments than in the first.
    submissions_with_period = (
        db_session.query(AssignmentSubmissionModel, AcademicPeriodModel.order_index)
        .join(AssignmentModel, AssignmentSubmissionModel.assignment_id == AssignmentModel.id)
        .join(AcademicPeriodModel, AssignmentModel.period_id == AcademicPeriodModel.id)
        .filter(AssignmentSubmissionModel.student_id == student.id)
        .all()
    )
    by_period_submission: dict[int, list] = defaultdict(list)
    for submission, order_index in submissions_with_period:
        by_period_submission[order_index].append(submission.status)

    first_statuses = by_period_submission[min(by_period_submission)]
    last_statuses = by_period_submission[max(by_period_submission)]

    def _not_delivered_share(statuses):
        return sum(1 for s in statuses if s.value == "NOT_DELIVERED") / len(statuses)

    assert _not_delivered_share(last_statuses) > _not_delivered_share(first_statuses)


# ---------------------------------------------------------------------------
# At least one STABLE member shows no trend (AC: "at least one changes
# nothing")
# ---------------------------------------------------------------------------


def test_stable_student_attendance_has_no_strong_trend(db_session: Session) -> None:
    _seed_periods(db_session)
    _seed_coordination_user(db_session)
    run_generation(db_session, _CONFIG, reset=False)

    student = (
        db_session.query(StudentModel)
        .filter(StudentModel.synthetic_profile == SyntheticProfile.STABLE)
        .first()
    )
    assert student is not None

    records = (
        db_session.query(AttendanceRecordModel)
        .filter(AttendanceRecordModel.student_id == student.id)
        .order_by(AttendanceRecordModel.date)
        .all()
    )
    quarter = len(records) // 4

    def _presence_rate(rows):
        return sum(1 for r in rows if r.status == AttendanceStatus.PRESENT) / len(rows)

    first_rate = _presence_rate(records[:quarter])
    last_rate = _presence_rate(records[-quarter:])
    # Same constant probability throughout — any gap is sampling noise, not
    # a systematic decline.
    assert abs(first_rate - last_rate) < 0.25
