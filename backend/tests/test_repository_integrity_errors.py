"""Repository-level translation of Postgres integrity violations
(`app/infrastructure/repositories/errors.py`).

Closes the `deferred-work.md` entry open since Story 1.5: "no repository
translates an `IntegrityError` into a domain error, so deleting a referenced
student/user later would surface as an unhandled 500". Two things were
actually wrong, and this file covers both:

1. the caller received an untyped driver exception it could not branch on —
   now it receives a `UniqueViolationError`/`ForeignKeyViolationError`
   naming the violated constraint, with the original exception preserved as
   `__cause__` (the source is never discarded);
2. only `SqlAlchemyAttendanceRepository.save` rolled back, so on every other
   write path a single failure left the `Session` in the "deactivated
   transaction" state and *every later statement on it* raised
   `PendingRollbackError` — one bad write poisoned the whole session.

The HTTP contract is deliberately unchanged by all of this: these errors
still subclass `sqlalchemy.exc.IntegrityError`, so `RegisterAttendanceService`
keeps answering 409 for a duplicate attendance exactly as before (proven by
`test_attendance.py`'s existing duplicate tests, untouched).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.attendance import AttendanceStatus
from app.infrastructure.db.models import ClassroomModel, StudentModel
from app.infrastructure.repositories.errors import (
    ForeignKeyViolationError,
    RepositoryIntegrityError,
    UniqueViolationError,
)
from app.infrastructure.repositories.sqlalchemy_attendance_repository import (
    SqlAlchemyAttendanceRepository,
)
from app.infrastructure.repositories.sqlalchemy_grade_repository import SqlAlchemyGradeRepository
from app.infrastructure.repositories.sqlalchemy_pedagogical_observation_repository import (
    SqlAlchemyPedagogicalObservationRepository,
)

DAY = date(2026, 9, 24)


def test_duplicate_attendance_raises_unique_violation_naming_the_constraint(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    repository = SqlAlchemyAttendanceRepository(db_session)
    repository.save(seeded_enrolled_student.id, seeded_classroom.id, DAY, AttendanceStatus.PRESENT)

    with pytest.raises(UniqueViolationError) as excinfo:
        repository.save(
            seeded_enrolled_student.id, seeded_classroom.id, DAY, AttendanceStatus.ABSENT_JUSTIFIED
        )

    error = excinfo.value
    assert error.constraint_name == "uq_attendance_student_classroom_date"
    assert error.table_name == "attendance_records"
    # The source is never discarded: the original driver exception stays
    # reachable as __cause__ (AGENTS.md "Evidência").
    assert isinstance(error.__cause__, IntegrityError)


def test_unique_violation_is_still_an_integrity_error_so_the_409_path_is_unchanged(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    """`RegisterAttendanceService` catches `sqlalchemy.exc.IntegrityError` to
    raise `DuplicateAttendanceError`. Translating at the repository must not
    silently break that — hence the deliberate subclassing documented in
    `repositories/errors.py`."""
    repository = SqlAlchemyAttendanceRepository(db_session)
    repository.save(seeded_enrolled_student.id, seeded_classroom.id, DAY, AttendanceStatus.PRESENT)

    with pytest.raises(IntegrityError):
        repository.save(
            seeded_enrolled_student.id, seeded_classroom.id, DAY, AttendanceStatus.PRESENT
        )


def test_grade_save_against_unknown_classroom_raises_foreign_key_violation(
    db_session: Session,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period,
) -> None:
    """Before this change this was a raw `IntegrityError` escaping the
    repository — an unhandled 500 with no way for a caller to tell an FK
    violation from a duplicate."""
    repository = SqlAlchemyGradeRepository(db_session)

    with pytest.raises(ForeignKeyViolationError) as excinfo:
        repository.save(
            student_id=seeded_enrolled_student.id,
            classroom_id=uuid.uuid4(),  # never inserted
            subject="Matemática",
            period_id=seeded_academic_period.id,
            date_=DAY,
            value=Decimal("7.00"),
        )

    assert excinfo.value.table_name == "grades"
    assert isinstance(excinfo.value, RepositoryIntegrityError)


def test_observation_save_against_unknown_author_raises_foreign_key_violation(
    db_session: Session,
    seeded_enrolled_student: StudentModel,
) -> None:
    from datetime import UTC, datetime

    repository = SqlAlchemyPedagogicalObservationRepository(db_session)

    with pytest.raises(ForeignKeyViolationError):
        repository.save(
            student_id=seeded_enrolled_student.id,
            author_user_id=uuid.uuid4(),  # never inserted
            text="Observação de teste.",
            created_at=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
        )


def test_session_stays_usable_after_a_failed_write_on_a_non_attendance_path(
    db_session: Session,
    seeded_enrolled_student: StudentModel,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
) -> None:
    """The regression that actually bit: only the attendance repository used
    to roll back. On every other write path the failed `commit()` left the
    session's transaction *deactivated*, so the next statement — any
    statement, including a plain read — raised `PendingRollbackError` instead
    of doing its job. Now the rollback is part of the translation, so the
    caller can keep working with the same session."""
    repository = SqlAlchemyGradeRepository(db_session)

    with pytest.raises(ForeignKeyViolationError):
        repository.save(
            student_id=seeded_enrolled_student.id,
            classroom_id=uuid.uuid4(),
            subject="Matemática",
            period_id=seeded_academic_period.id,
            date_=DAY,
            value=Decimal("7.00"),
        )

    # Would raise PendingRollbackError before the fix.
    student_name = db_session.execute(
        select(StudentModel.name).where(StudentModel.id == seeded_enrolled_student.id)
    ).scalar_one()
    assert student_name == seeded_enrolled_student.name

    # And a subsequent *valid* write on the same session still succeeds.
    saved = repository.save(
        student_id=seeded_enrolled_student.id,
        classroom_id=seeded_classroom.id,
        subject="Matemática",
        period_id=seeded_academic_period.id,
        date_=DAY,
        value=Decimal("7.00"),
    )
    assert saved.value == Decimal("7.00")
