"""Idempotent dev-only CLI seeding 2 classrooms + ~8 students each (all
`EVAL_DEMO`) + their enrollments.

Usage:
    python -m app.infrastructure.db.seed_dev_fixtures

There is no classroom/student/enrollment CRUD screen — this script is the
only way this fixture data ever gets created (spec Boundaries &
Constraints: "classrooms/students/enrollments come only from a dev seed
script, never a registration UI"). Re-running with the fixture already
present is a no-op.
"""

from __future__ import annotations

import sys

from sqlalchemy.exc import IntegrityError

from app.domain.student import DatasetSplit
from app.infrastructure.db.base import SessionLocal
from app.infrastructure.db.models import ClassroomModel, EnrollmentModel, StudentModel

_ACADEMIC_YEAR = 2026

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


def seed_dev_fixtures() -> None:
    with SessionLocal() as session:
        existing_count = session.query(ClassroomModel).count()
        if existing_count > 0:
            print("Dev fixtures already exist — no-op.")
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
            print("Dev fixtures already exist — no-op.")
            return

        print(
            f"Seeded {len(_FIXTURES)} classrooms with "
            f"{sum(len(names) for _, names in _FIXTURES)} students."
        )


if __name__ == "__main__":
    seed_dev_fixtures()
    sys.exit(0)
