"""The synthetic generator CLI — `python -m app.synthetic.generate --seed N`.

Persists through SQLAlchemy models and a `Session` (the `seed_dev_fixtures.py`
CLI precedent), never a hand-rolled SQL string. Refuses to run against a
populated database without an explicit `--reset` (D4) — silently appending
would both violate `AttendanceRecord`'s `UNIQUE` constraint in later stories
and destroy the determinism guarantee in the same stroke.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.infrastructure.db.base import SessionLocal
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    AssignmentModel,
    AssignmentSubmissionModel,
    AttendanceRecordModel,
    ClassroomModel,
    EnrollmentModel,
    GradeModel,
    PedagogicalObservationModel,
    StudentModel,
    SyntheticGenerationRunModel,
    UserModel,
)
from app.synthetic import facts, observations
from app.synthetic.facts import PeriodWindow
from app.synthetic.fingerprint import population_fingerprint
from app.synthetic.population import GenerationConfig, build_population

#: Hand-maintained — bumped by any story that changes what the generator
#: emits, so an old `synthetic_generation_runs` row stays interpretable after
#: the generator evolves (RNF-13, Assumption 4).
GENERATOR_VERSION = "2.5.0"


class DatabasePopulatedError(RuntimeError):
    """Raised when the database already holds generated data and `--reset`
    was not passed. The message is also what the CLI prints to stderr."""


class MissingAcademicPeriodsError(RuntimeError):
    """Raised when no `academic_periods` row exists for `config.academic_year`.

    The generator never creates or modifies `academic_periods` (owned by
    `seed_dev_fixtures.py`) — it fails clearly instead of silently writing
    an incomplete or inconsistent base (spec Boundaries & Constraints, I/O
    Matrix "No periods seeded" row)."""


class MissingAuthorUserError(RuntimeError):
    """Raised when no `UserModel` row has `email == get_settings().dev_seed_email`.

    Synthetic `PedagogicalObservationModel` rows need a real `author_user_id`
    FK; the generator never invents a user, so it fails before writing
    anything instead of silently producing an unattributable observation
    (spec I/O Matrix "No UserModel row with email == dev_seed_email" row)."""


def is_populated(session: Session) -> bool:
    """"Already populated" means any row in `classrooms`, `students`,
    `enrollments` or `synthetic_generation_runs` (Assumption 5) — a database
    holding only `users`/`academic_periods` (the other seed scripts' output)
    is treated as clean."""
    for model in (ClassroomModel, StudentModel, EnrollmentModel, SyntheticGenerationRunModel):
        if session.query(model).first() is not None:
            return True
    return False


def reset_generated_data(session: Session) -> None:
    """Deletes, in FK-safe order, every table a synthetic base owns or that
    would dangle without students/classrooms (Design Notes: "--reset scope").
    Never touches `users` or `academic_periods` — each is owned and re-seeded
    by its own idempotent script.

    Deliberately leaves `synthetic_generation_runs` alone: it is provenance
    *history*, not generated-base content, and the I/O matrix (frozen,
    human-approved) requires a second row to exist after a same-seed re-run
    with `--reset` — wiping it here would make RNF-13's audit trail
    unreconstructable across resets.

    Does not commit: the caller (`run_generation`) commits the deletes
    together with the regenerated rows, as one transaction, so a failure
    partway through population construction or insertion leaves the
    database exactly as it was before `--reset` ran."""
    session.query(AssignmentSubmissionModel).delete()
    session.query(AssignmentModel).delete()
    session.query(GradeModel).delete()
    session.query(AttendanceRecordModel).delete()
    session.query(PedagogicalObservationModel).delete()
    session.query(EnrollmentModel).delete()
    session.query(StudentModel).delete()
    session.query(ClassroomModel).delete()


def _resolve_author_user_id(session: Session) -> uuid.UUID:
    """Resolves the single `COORDENACAO_PEDAGOGICA` user seeded by
    `seed_dev_user.py` to attribute every generated `PedagogicalObservation`
    to. Looked up by `get_settings().dev_seed_email`, normalized the same
    way `seed_dev_user.py` normalizes it before storing (`.strip().lower()`)
    so the lookup matches regardless of how the setting's raw value was
    cased/spaced. The only place in this module that imports settings or
    queries `UserModel` (spec Code Map)."""
    settings = get_settings()
    if not settings.dev_seed_email:
        raise MissingAuthorUserError(
            "DEV_SEED_EMAIL is not configured — cannot resolve the coordination "
            "user to attribute synthetic observations to. Set DEV_SEED_EMAIL and "
            "run `python -m app.infrastructure.db.seed_dev_user` first."
        )

    email = settings.dev_seed_email.strip().lower()
    user = session.query(UserModel).filter(UserModel.email == email).one_or_none()
    if user is None:
        raise MissingAuthorUserError(
            f"No users row found with email={email!r}. Run "
            "`python -m app.infrastructure.db.seed_dev_user` first."
        )
    return user.id


def run_generation(
    session: Session, config: GenerationConfig, reset: bool
) -> tuple[str, SyntheticGenerationRunModel]:
    """Generates `config`'s population into `session` and returns
    `(fingerprint, run)`. Takes a `Session` parameter (not `SessionLocal`
    directly) so the test suite can drive it inside its own rolled-back
    transaction."""
    # The school calendar is built strictly from existing `AcademicPeriod`
    # rows for `config.academic_year` — queried, never created or modified
    # here (spec Boundaries & Constraints). `AcademicPeriodModel` has no
    # `academic_year` column of its own (data-model.md), so "for
    # config.academic_year" is read as "whose start_date falls in that
    # calendar year" — true of every period `seed_dev_fixtures.py` seeds.
    #
    # Checked *before* `is_populated`/`reset_generated_data` below: a
    # populated database + `--reset` + periods missing/wrong-year must still
    # write nothing, not leave the session holding uncommitted deletes from
    # a reset that started before this validation ran.
    period_rows = (
        session.query(AcademicPeriodModel).order_by(AcademicPeriodModel.order_index).all()
    )
    matching_periods = [p for p in period_rows if p.start_date.year == config.academic_year]
    if not matching_periods:
        raise MissingAcademicPeriodsError(
            f"No academic_periods rows found for academic_year={config.academic_year}. "
            "Run `python -m app.infrastructure.db.seed_dev_fixtures` first to seed them."
        )

    order_indexes = [period.order_index for period in matching_periods]
    if len(order_indexes) != len(set(order_indexes)):
        duplicates = sorted({i for i in order_indexes if order_indexes.count(i) > 1})
        raise ValueError(
            f"Duplicate academic_periods.order_index values for academic_year="
            f"{config.academic_year}: {duplicates}. Each period must have a unique "
            "order_index — the generator uses it to attribute grades/assignments to "
            "the correct period."
        )

    # Resolved before `is_populated`/`reset_generated_data` below, for the
    # same reason the periods check above runs first: a populated database +
    # `--reset` + no coordination user must still write nothing, not leave
    # the session holding uncommitted deletes from a reset that started
    # before this validation ran (spec I/O Matrix "No UserModel row with
    # email == dev_seed_email" row).
    author_user_id = _resolve_author_user_id(session)

    if is_populated(session):
        if not reset:
            raise DatabasePopulatedError(
                "Database already populated — pass --reset to wipe and regenerate."
            )
        reset_generated_data(session)

    period_windows = tuple(
        PeriodWindow(
            id_label=f"period-{period.order_index}",
            start_date=period.start_date,
            end_date=period.end_date,
            order_index=period.order_index,
        )
        for period in matching_periods
    )
    period_id_by_order_index = {period.order_index: period.id for period in matching_periods}

    population = build_population(config)

    for classroom in population.classrooms:
        session.add(
            ClassroomModel(
                id=classroom.id, name=classroom.name, academic_year=classroom.academic_year
            )
        )
    session.flush()

    for student in population.students:
        session.add(
            StudentModel(
                id=student.id,
                name=student.name,
                dataset_split=student.dataset_split,
                synthetic_profile=student.synthetic_profile,
            )
        )
    session.flush()

    for enrollment in population.enrollments:
        session.add(
            EnrollmentModel(
                id=enrollment.id,
                student_id=enrollment.student_id,
                classroom_id=enrollment.classroom_id,
            )
        )
    session.flush()

    generated_facts = facts.build_facts(population, period_windows, config)

    for record in generated_facts.attendance_records:
        session.add(
            AttendanceRecordModel(
                id=record.id,
                student_id=record.student_id,
                classroom_id=record.classroom_id,
                date=record.date,
                status=record.status,
            )
        )
    session.flush()

    for grade in generated_facts.grades:
        session.add(
            GradeModel(
                id=grade.id,
                student_id=grade.student_id,
                classroom_id=grade.classroom_id,
                subject=grade.subject,
                period_id=period_id_by_order_index[grade.period_order_index],
                date=grade.date,
                value=grade.value,
            )
        )
    session.flush()

    for assignment in generated_facts.assignments:
        session.add(
            AssignmentModel(
                id=assignment.id,
                classroom_id=assignment.classroom_id,
                subject=assignment.subject,
                period_id=period_id_by_order_index[assignment.period_order_index],
                due_date=assignment.due_date,
            )
        )
    session.flush()

    for submission in generated_facts.assignment_submissions:
        session.add(
            AssignmentSubmissionModel(
                id=submission.id,
                assignment_id=submission.assignment_id,
                student_id=submission.student_id,
                status=submission.status,
                date=submission.date,
            )
        )
    session.flush()

    generated_observations = observations.build_observations(
        population, period_windows, author_user_id, config.seed
    )
    for observation in generated_observations:
        session.add(
            PedagogicalObservationModel(
                id=observation.id,
                student_id=observation.student_id,
                author_user_id=observation.author_user_id,
                text=observation.text,
                created_at=observation.created_at,
            )
        )
    session.flush()

    run = SyntheticGenerationRunModel(
        seed=config.seed,
        generator_version=GENERATOR_VERSION,
        executed_at=datetime.now(timezone.utc),
        student_count=len(population.students),
        train_ratio=Decimal(str(config.train_ratio)),
    )
    session.add(run)
    session.commit()

    fingerprint = population_fingerprint(session)
    return fingerprint, run


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {value!r}")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {value!r}")
    return parsed


def _open_unit_interval(value: str) -> float:
    parsed = float(value)
    if not (0 < parsed < 1):
        raise argparse.ArgumentTypeError(f"must be strictly between 0 and 1, got {value!r}")
    return parsed


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.synthetic.generate",
        description="Deterministically generate a synthetic base of classrooms, students and enrollments.",
    )
    parser.add_argument("--seed", type=_non_negative_int, required=True)
    parser.add_argument("--students", type=_positive_int, default=200, dest="student_count")
    parser.add_argument(
        "--students-per-classroom", type=_positive_int, default=25, dest="students_per_classroom"
    )
    parser.add_argument(
        "--train-ratio", type=_open_unit_interval, default=0.7, dest="train_ratio"
    )
    parser.add_argument(
        "--academic-year", type=_positive_int, default=2026, dest="academic_year"
    )
    parser.add_argument("--reset", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_arg_parser().parse_args(argv)

    config = GenerationConfig(
        seed=args.seed,
        student_count=args.student_count,
        students_per_classroom=args.students_per_classroom,
        train_ratio=args.train_ratio,
        academic_year=args.academic_year,
    )

    with SessionLocal() as session:
        try:
            fingerprint, run = run_generation(session, config, reset=args.reset)
        except DatabasePopulatedError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        except MissingAcademicPeriodsError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        except MissingAuthorUserError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)

        # Read everything needed for the summary before the session (and
        # therefore the ORM instance) closes at the end of this block.
        summary = (
            f"Generated {run.student_count} students "
            f"(seed={run.seed}, generator_version={run.generator_version}, "
            f"train_ratio={run.train_ratio})"
        )

    print(summary)
    print(f"Fingerprint: {fingerprint}")
    sys.exit(0)


if __name__ == "__main__":
    main()
