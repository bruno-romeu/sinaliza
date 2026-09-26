"""Idempotent dev-only CLI seeding 2 classrooms + ~8 students each (all
`EVAL_DEMO`) + their enrollments, plus 4 `AcademicPeriod` bimesters (Story
1.3).

Usage:
    python -m app.infrastructure.db.seed_dev_fixtures

There is no classroom/student/enrollment/academic-period CRUD screen — this
script is the only way this fixture data ever gets created (spec Boundaries
& Constraints). Classroom/student/enrollment seeding and academic-period
seeding are each independently idempotent (checked by their own row count),
so re-running is always a no-op regardless of which half already ran —
this matters because a worktree that already has classrooms seeded from
Story 1.2 must still get academic periods seeded by this story's addition.
"""

from __future__ import annotations

import sys
from datetime import date

from sqlalchemy.exc import IntegrityError

from app.domain.student import DatasetSplit
from app.infrastructure.db.base import SessionLocal
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    ClassroomModel,
    EnrollmentModel,
    StudentModel,
)

_ACADEMIC_YEAR = 2026

# 4 bimesters for academic_year=2026 (spec Design Notes). "3º Bimestre"
# deliberately contains 2026-09-24 (today) so "período letivo vigente" holds
# for manual verification without a period-registration screen.
_ACADEMIC_PERIODS: list[tuple[str, date, date, int]] = [
    ("1º Bimestre", date(2026, 2, 2), date(2026, 4, 17), 1),
    ("2º Bimestre", date(2026, 4, 20), date(2026, 6, 26), 2),
    ("3º Bimestre", date(2026, 7, 27), date(2026, 9, 25), 3),
    ("4º Bimestre", date(2026, 9, 28), date(2026, 12, 18), 4),
]

_FIXTURES: list[tuple[str, list[str]]] = [
    (
        "6º Ano A",
        [
            "Ana Beatriz Souza",
            "Bruno Carvalho Lima",
            "Camila Ferreira Alves",
            "Daniel Pereira Rocha",
            "Eduarda Martins Costa",
            "Felipe Ribeiro Santos",
            "Gabriela Nascimento Dias",
            "Henrique Oliveira Barros",
        ],
    ),
    (
        "6º Ano B",
        [
            "Isabela Cardoso Teixeira",
            "João Vitor Almeida",
            "Larissa Gomes Pinto",
            "Matheus Araújo Correia",
            "Natália Fernandes Moura",
            "Otávio Cunha Ramos",
            "Paula Rodrigues Vieira",
            "Rafael Batista Monteiro",
        ],
    ),
]


def _seed_classrooms_students_enrollments(session) -> None:
    existing_count = session.query(ClassroomModel).count()
    if existing_count > 0:
        print("Classrooms/students/enrollments already exist — no-op.")
        return

    for classroom_name, student_names in _FIXTURES:
        classroom = ClassroomModel(name=classroom_name, academic_year=_ACADEMIC_YEAR)
        session.add(classroom)
        session.flush()  # assigns classroom.id without committing yet

        for student_name in student_names:
            student = StudentModel(name=student_name, dataset_split=DatasetSplit.EVAL_DEMO)
            session.add(student)
            session.flush()  # assigns student.id

            session.add(EnrollmentModel(student_id=student.id, classroom_id=classroom.id))

    try:
        session.commit()
    except IntegrityError:
        # Lost a race with a concurrent run of this same script — same
        # outcome as the "already exists" no-op path above, not a crash.
        session.rollback()
        print("Classrooms/students/enrollments already exist — no-op.")
        return

    print(
        f"Seeded {len(_FIXTURES)} classrooms with "
        f"{sum(len(names) for _, names in _FIXTURES)} students."
    )


def _seed_academic_periods(session) -> None:
    existing_count = session.query(AcademicPeriodModel).count()
    if existing_count > 0:
        print("Academic periods already exist — no-op.")
        return

    for label, start_date, end_date, order_index in _ACADEMIC_PERIODS:
        session.add(
            AcademicPeriodModel(
                label=label,
                start_date=start_date,
                end_date=end_date,
                order_index=order_index,
            )
        )

    try:
        session.commit()
    except IntegrityError:
        # Lost a race with a concurrent run of this same script — same
        # outcome as the "already exists" no-op path above, not a crash.
        session.rollback()
        print("Academic periods already exist — no-op.")
        return

    print(f"Seeded {len(_ACADEMIC_PERIODS)} academic periods.")


def seed_dev_fixtures() -> None:
    with SessionLocal() as session:
        _seed_classrooms_students_enrollments(session)
        _seed_academic_periods(session)


if __name__ == "__main__":
    seed_dev_fixtures()
    sys.exit(0)
