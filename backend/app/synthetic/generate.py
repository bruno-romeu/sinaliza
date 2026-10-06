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
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.infrastructure.db.base import SessionLocal
from app.infrastructure.db.models import (
    AssignmentModel,
    AssignmentSubmissionModel,
    AttendanceRecordModel,
    ClassroomModel,
    EnrollmentModel,
    GradeModel,
    PedagogicalObservationModel,
    StudentModel,
    SyntheticGenerationRunModel,
)
from app.synthetic.fingerprint import population_fingerprint
from app.synthetic.population import GenerationConfig, build_population

#: Hand-maintained — bumped by any story that changes what the generator
#: emits, so an old `synthetic_generation_runs` row stays interpretable after
#: the generator evolves (RNF-13, Assumption 4).
GENERATOR_VERSION = "2.1.0"


class DatabasePopulatedError(RuntimeError):
    """Raised when the database already holds generated data and `--reset`
    was not passed. The message is also what the CLI prints to stderr."""


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


def run_generation(
    session: Session, config: GenerationConfig, reset: bool
) -> tuple[str, SyntheticGenerationRunModel]:
    """Generates `config`'s population into `session` and returns
    `(fingerprint, run)`. Takes a `Session` parameter (not `SessionLocal`
    directly) so the test suite can drive it inside its own rolled-back
    transaction."""
    if is_populated(session):
        if not reset:
            raise DatabasePopulatedError(
                "Database already populated — pass --reset to wipe and regenerate."
            )
        reset_generated_data(session)

    population = build_population(config)

    for classroom in population.classrooms:
        session.add(
            ClassroomModel(
                id=classroom.id, name=classroom.name, academic_year=classroom.academic_year
            )
        )
    session.flush()

    for student in population.students:
        # `synthetic_profile` is left NULL — Story 2.2 owns populating it
        # (spec Boundaries & Constraints).
        session.add(
            StudentModel(
                id=student.id,
                name=student.name,
                dataset_split=student.dataset_split,
                synthetic_profile=None,
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
