"""Pure template/selection tests for `app.synthetic.observations` (no
database, mirrors `test_synthetic_profiles.py`'s precedent) plus DB-wiring
tests covering the spec's I/O & Edge-Case Matrix and Acceptance Criteria.

Defines its own local helper to seed the coordination user at
`get_settings().dev_seed_email`, mirroring `_seed_academic_periods` in
`test_synthetic_generation.py` (spec Code Map: "do not touch conftest.py").
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime, time
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.student import DatasetSplit, SyntheticProfile
from app.domain.user import UserRole
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    PedagogicalObservationModel,
    StudentModel,
    UserModel,
)
from app.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher
from app.synthetic import observations
from app.synthetic.facts import PeriodWindow
from app.synthetic.fingerprint import population_fingerprint
from app.synthetic.generate import (
    GENERATOR_VERSION,
    MissingAuthorUserError,
    run_generation,
)
from app.synthetic.population import (
    GeneratedClassroom,
    GeneratedEnrollment,
    GeneratedPopulation,
    GeneratedStudent,
    GenerationConfig,
)

SEED = 777

# A judgment-label vocabulary scan (spec AC 4 / EXPERIENCE.md Voice and
# Tone): none of these may ever appear in generated observation text.
_BANNED_PATTERN = re.compile(r"risco|evas[ãa]o|abandono|alerta|%|chance de", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Shared helpers (pure)
# ---------------------------------------------------------------------------


def _student(profile: SyntheticProfile) -> GeneratedStudent:
    return GeneratedStudent(
        id=uuid.uuid4(),
        name="Estudante Teste",
        dataset_split=DatasetSplit.EVAL_DEMO,
        synthetic_profile=profile,
    )


def _population(*profiles: SyntheticProfile) -> GeneratedPopulation:
    classroom = GeneratedClassroom(id=uuid.uuid4(), name="Turma Teste", academic_year=2026)
    students = [_student(profile) for profile in profiles]
    enrollments = [
        GeneratedEnrollment(id=uuid.uuid4(), student_id=s.id, classroom_id=classroom.id)
        for s in students
    ]
    return GeneratedPopulation(
        classrooms=(classroom,), students=tuple(students), enrollments=tuple(enrollments)
    )


def _periods(count: int) -> tuple[PeriodWindow, ...]:
    return tuple(
        PeriodWindow(
            id_label=f"period-{i + 1}",
            start_date=date(2026, 2 + i, 1),
            end_date=date(2026, 2 + i, 28),
            order_index=i + 1,
        )
        for i in range(count)
    )


# ---------------------------------------------------------------------------
# Pure: determinism + shape
# ---------------------------------------------------------------------------


def test_build_observations_is_deterministic() -> None:
    population = _population(*SyntheticProfile)
    periods = _periods(4)
    author_id = uuid.uuid4()

    result_1 = observations.build_observations(population, periods, author_id, SEED)
    result_2 = observations.build_observations(population, periods, author_id, SEED)

    assert result_1 == result_2


def test_build_observations_one_per_student_period() -> None:
    population = _population(*SyntheticProfile)
    periods = _periods(4)
    author_id = uuid.uuid4()

    result = observations.build_observations(population, periods, author_id, SEED)

    assert len(result) == len(population.students) * len(periods)
    keys = [(o.student_id, o.id) for o in result]
    assert len(keys) == len(set(keys))


def test_build_observations_different_seed_changes_text() -> None:
    population = _population(SyntheticProfile.FALLING_ATTENDANCE)
    periods = _periods(4)
    author_id = uuid.uuid4()

    result_a = observations.build_observations(population, periods, author_id, 1)
    result_b = observations.build_observations(population, periods, author_id, 2)

    texts_a = [o.text for o in result_a]
    texts_b = [o.text for o in result_b]
    assert texts_a != texts_b


def test_build_observations_created_at_is_noon_utc_on_period_end_date() -> None:
    population = _population(SyntheticProfile.STABLE)
    periods = _periods(2)
    author_id = uuid.uuid4()

    result = observations.build_observations(population, periods, author_id, SEED)

    for observation, period in zip(
        sorted(result, key=lambda o: o.created_at), sorted(periods, key=lambda p: p.end_date)
    ):
        assert observation.created_at == datetime.combine(period.end_date, time(12, 0), tzinfo=UTC)


def test_build_observations_author_user_id_is_carried_through() -> None:
    population = _population(SyntheticProfile.STABLE)
    periods = _periods(1)
    author_id = uuid.uuid4()

    result = observations.build_observations(population, periods, author_id, SEED)
    assert all(o.author_user_id == author_id for o in result)


# ---------------------------------------------------------------------------
# Pure: profile-vocabulary isolation (AC 1, AC 2)
# ---------------------------------------------------------------------------


def test_stable_profile_only_uses_routine_templates() -> None:
    population = _population(SyntheticProfile.STABLE)
    periods = _periods(6)
    author_id = uuid.uuid4()

    result = observations.build_observations(population, periods, author_id, SEED)

    for observation in result:
        assert observation.text in observations._ROUTINE_TEMPLATES


def test_falling_attendance_only_uses_attendance_decline_templates_by_stage() -> None:
    population = _population(SyntheticProfile.FALLING_ATTENDANCE)
    periods = _periods(6)
    author_id = uuid.uuid4()
    student_id = population.students[0].id

    result = observations.build_observations(population, periods, author_id, SEED)

    all_decline_texts = {
        text for stage_set in observations._ATTENDANCE_DECLINE_TEMPLATES.values() for text in stage_set
    }
    for period_index, observation in enumerate(result):
        assert observation.text in all_decline_texts
        assert observation.text not in observations._ROUTINE_TEMPLATES
        stage = observations._stage(observations._progress(period_index, len(periods)))
        assert observation.text in observations._ATTENDANCE_DECLINE_TEMPLATES[stage]
    assert student_id == population.students[0].id  # sanity: single-student population


def test_falling_grades_only_uses_performance_decline_templates_by_stage() -> None:
    population = _population(SyntheticProfile.FALLING_GRADES)
    periods = _periods(6)
    author_id = uuid.uuid4()

    result = observations.build_observations(population, periods, author_id, SEED)

    for period_index, observation in enumerate(result):
        stage = observations._stage(observations._progress(period_index, len(periods)))
        assert observation.text in observations._PERFORMANCE_DECLINE_TEMPLATES[stage]
        assert observation.text not in observations._ROUTINE_TEMPLATES


def test_combined_deterioration_composes_attendance_and_assignment_fragments() -> None:
    population = _population(SyntheticProfile.COMBINED_DETERIORATION)
    periods = _periods(6)
    author_id = uuid.uuid4()

    result = observations.build_observations(population, periods, author_id, SEED)

    for period_index, observation in enumerate(result):
        stage = observations._stage(observations._progress(period_index, len(periods)))
        assert observation.text.startswith(observations._COMBINED_PREFIX)
        assert " e " in observation.text
        attendance_options = observations._COMBINED_ATTENDANCE_FRAGMENTS[stage]
        assignment_options = observations._COMBINED_ASSIGNMENT_FRAGMENTS[stage]
        assert any(fragment in observation.text for fragment in attendance_options)
        assert any(fragment in observation.text for fragment in assignment_options)
        # Never restates a grade/number — only the two behavioral signals
        # (Design Notes: "narrates the two behavioral signals").
        assert not any(char.isdigit() for char in observation.text)


def test_stage_mirrors_profiles_progress_division_by_zero_handling() -> None:
    # Single-period school year: progress is 1.0 (never a ZeroDivisionError),
    # same as `profiles.py::_progress` (Assumption 3).
    assert observations._progress(0, 1) == 1.0
    assert observations._stage(observations._progress(0, 1)) == "late"


# ---------------------------------------------------------------------------
# Pure: no judgment-label vocabulary anywhere in any template set (AC 4)
# ---------------------------------------------------------------------------


def _all_template_strings() -> list[str]:
    strings: list[str] = list(observations._ROUTINE_TEMPLATES)
    for mapping in (
        observations._ATTENDANCE_DECLINE_TEMPLATES,
        observations._PERFORMANCE_DECLINE_TEMPLATES,
        observations._COMBINED_ATTENDANCE_FRAGMENTS,
        observations._COMBINED_ASSIGNMENT_FRAGMENTS,
    ):
        for options in mapping.values():
            strings.extend(options)
    strings.append(observations._COMBINED_PREFIX)
    return strings


def test_no_judgment_label_vocabulary_in_any_template() -> None:
    for text in _all_template_strings():
        assert not _BANNED_PATTERN.search(text), text


def test_no_judgment_label_vocabulary_in_any_generated_observation() -> None:
    population = _population(*SyntheticProfile)
    periods = _periods(6)
    author_id = uuid.uuid4()

    result = observations.build_observations(population, periods, author_id, SEED)
    for observation in result:
        assert not _BANNED_PATTERN.search(observation.text), observation.text


def test_every_template_set_is_a_plain_tuple_of_literal_strings() -> None:
    for text in _all_template_strings():
        assert isinstance(text, str)
        # No digit anywhere — no fabricated statistic baked into a template.
        assert not any(char.isdigit() for char in text), text


# ---------------------------------------------------------------------------
# DB wiring
# ---------------------------------------------------------------------------


def _seed_academic_periods(db_session: Session, academic_year: int = 2026) -> None:
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
            AcademicPeriodModel(
                label="3º Bimestre",
                start_date=date(academic_year, 7, 27),
                end_date=date(academic_year, 9, 25),
                order_index=3,
            ),
        ]
    )
    db_session.commit()


def _seed_coordination_user(db_session: Session) -> UserModel:
    """Seeds the `COORDENACAO_PEDAGOGICA` user at
    `get_settings().dev_seed_email`, normalized the same way
    `seed_dev_user.py` normalizes it — the exact row `generate.py`'s
    `_resolve_author_user_id` must find."""
    settings = get_settings()
    assert settings.dev_seed_email, (
        "DEV_SEED_EMAIL must be configured (via backend/.env) for this test suite to run"
    )
    email = settings.dev_seed_email.strip().lower()
    hasher = BcryptPasswordHasher()
    user = UserModel(
        name=settings.dev_seed_name,
        email=email,
        password_hash=hasher.hash("Senha-Correta-123"),
        role=UserRole.COORDENACAO_PEDAGOGICA,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


_REDUCED_CONFIG = GenerationConfig(seed=42, student_count=12, students_per_classroom=4, train_ratio=0.5)


def test_run_generation_creates_one_observation_per_student_period(db_session: Session) -> None:
    _seed_academic_periods(db_session)
    user = _seed_coordination_user(db_session)

    run_generation(db_session, _REDUCED_CONFIG, reset=False)

    students = db_session.query(StudentModel).all()
    observation_rows = db_session.query(PedagogicalObservationModel).all()

    assert len(observation_rows) == len(students) * 3  # 3 periods seeded
    assert all(row.author_user_id == user.id for row in observation_rows)
    assert all(row.text for row in observation_rows)
    assert all(row.created_at is not None for row in observation_rows)


def test_run_generation_stable_student_observations_only_routine(db_session: Session) -> None:
    _seed_academic_periods(db_session)
    _seed_coordination_user(db_session)

    run_generation(db_session, _REDUCED_CONFIG, reset=False)

    student = (
        db_session.query(StudentModel)
        .filter(StudentModel.synthetic_profile == SyntheticProfile.STABLE)
        .first()
    )
    assert student is not None, "fixture seed/volume must produce at least one STABLE student"

    rows = (
        db_session.query(PedagogicalObservationModel)
        .filter(PedagogicalObservationModel.student_id == student.id)
        .all()
    )
    assert rows
    for row in rows:
        assert row.text in observations._ROUTINE_TEMPLATES
        assert not _BANNED_PATTERN.search(row.text)


def test_run_generation_falling_attendance_or_combined_student_uses_decline_text(
    db_session: Session,
) -> None:
    _seed_academic_periods(db_session)
    _seed_coordination_user(db_session)

    run_generation(db_session, _REDUCED_CONFIG, reset=False)

    decline_students = (
        db_session.query(StudentModel)
        .filter(
            StudentModel.synthetic_profile.in_(
                [SyntheticProfile.FALLING_ATTENDANCE, SyntheticProfile.COMBINED_DETERIORATION]
            )
        )
        .all()
    )
    assert decline_students, "fixture seed/volume must produce at least one decline-profile student"

    for student in decline_students:
        rows = (
            db_session.query(PedagogicalObservationModel)
            .filter(PedagogicalObservationModel.student_id == student.id)
            .all()
        )
        for row in rows:
            assert row.text not in observations._ROUTINE_TEMPLATES
            assert not _BANNED_PATTERN.search(row.text)


def test_missing_author_user_raises_before_any_row_written(db_session: Session) -> None:
    _seed_academic_periods(db_session)
    # Deliberately no coordination user seeded.

    with pytest.raises(MissingAuthorUserError):
        run_generation(db_session, _REDUCED_CONFIG, reset=False)

    assert db_session.query(StudentModel).count() == 0
    assert db_session.query(PedagogicalObservationModel).count() == 0


def test_populated_db_with_reset_but_author_user_missing_writes_nothing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: `_resolve_author_user_id` must run *before*
    # `is_populated`/`reset_generated_data` wipe anything (generate.py's own
    # comment on the call site), so a populated database + `--reset` + a
    # coordination-user lookup that no longer resolves still writes nothing —
    # the deletes must never start before the validation that can abort the
    # whole generation. Mirrors
    # `test_populated_db_with_reset_but_periods_missing_writes_nothing` in
    # `test_synthetic_generation.py`.
    _seed_academic_periods(db_session)
    _seed_coordination_user(db_session)
    run_generation(db_session, _REDUCED_CONFIG, reset=False)

    student_count_before = db_session.query(StudentModel).count()
    observation_count_before = db_session.query(PedagogicalObservationModel).count()

    # Simulate the lookup no longer resolving, without touching the already
    #-seeded user row (it is a real FK target of the first run's
    # observations, so deleting it would just hit a different constraint).
    monkeypatch.setattr(
        "app.synthetic.generate.get_settings",
        lambda: SimpleNamespace(dev_seed_email="outro-email@sinaliza.dev"),
    )

    with pytest.raises(MissingAuthorUserError):
        run_generation(db_session, _REDUCED_CONFIG, reset=True)

    # Nothing was wiped or regenerated: the pre-existing rows from the first
    # successful run are untouched.
    assert db_session.query(StudentModel).count() == student_count_before
    assert db_session.query(PedagogicalObservationModel).count() == observation_count_before


def test_reset_rerun_regenerates_observations_identically(db_session: Session) -> None:
    _seed_academic_periods(db_session)
    _seed_coordination_user(db_session)

    run_generation(db_session, _REDUCED_CONFIG, reset=False)
    texts_before = {
        (row.student_id, row.text, row.created_at)
        for row in db_session.query(PedagogicalObservationModel).all()
    }

    run_generation(db_session, _REDUCED_CONFIG, reset=True)
    texts_after = {
        (row.student_id, row.text, row.created_at)
        for row in db_session.query(PedagogicalObservationModel).all()
    }

    assert texts_before == texts_after


def test_fingerprint_excludes_author_user_id(db_session: Session) -> None:
    _seed_academic_periods(db_session)
    user_a = _seed_coordination_user(db_session)

    fingerprint_1, _ = run_generation(db_session, _REDUCED_CONFIG, reset=False)

    # Rewrite every observation's author_user_id to a different (but still
    # valid) user id, simulating "same seed, different coordination-user DB
    # id" (spec I/O Matrix, hypothetical cross-machine case) — without
    # re-running the whole generator.
    other_user = UserModel(
        name="Outra Coordenação",
        email="outra@escola.test",
        password_hash=BcryptPasswordHasher().hash("Outra-Senha-123"),
        role=UserRole.COORDENACAO_PEDAGOGICA,
    )
    db_session.add(other_user)
    db_session.flush()
    db_session.query(PedagogicalObservationModel).update(
        {PedagogicalObservationModel.author_user_id: other_user.id}
    )
    db_session.commit()

    fingerprint_2 = population_fingerprint(db_session)

    assert fingerprint_1 == fingerprint_2
    assert user_a.id != other_user.id


def test_fingerprint_changes_when_observation_text_changes(db_session: Session) -> None:
    _seed_academic_periods(db_session)
    _seed_coordination_user(db_session)

    fingerprint_1, _ = run_generation(db_session, _REDUCED_CONFIG, reset=False)

    row = db_session.query(PedagogicalObservationModel).first()
    row.text = "Texto alterado manualmente para este teste."
    db_session.commit()

    fingerprint_2 = population_fingerprint(db_session)
    assert fingerprint_1 != fingerprint_2


def test_generator_version_bumped_for_spec_ui_3() -> None:
    assert GENERATOR_VERSION == "2.6.0"
