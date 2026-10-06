"""Content fingerprint of the generated population — SHA-256 over a declared,
stably-ordered column list (Design Notes: "Fingerprint excludes
`executed_at`"). This, not row counts, is what RNF-13's determinism claim is
proven by: two generations of the same seed must hash identical, and two
generations of different seeds must hash different.

Extended (not rewritten) by later stories: Story 2.2/2.3/2.5 append their own
generated tables to the same declaration rather than replacing it.
"""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.infrastructure.db.models import ClassroomModel, EnrollmentModel, StudentModel


def population_fingerprint(session: Session) -> str:
    """SHA-256 hex digest over `classrooms`, `students` and `enrollments`,
    each read back in a stable `ORDER BY id` and a declared column list.
    Deliberately excludes `synthetic_generation_runs.executed_at` (wall-clock,
    never reproducible) and `students.synthetic_profile` (always NULL in this
    story; Story 2.2 extends the declaration when it starts populating it)."""
    hasher = hashlib.sha256()

    for classroom in session.query(ClassroomModel).order_by(ClassroomModel.id).all():
        hasher.update(
            f"classroom|{classroom.id}|{classroom.name}|{classroom.academic_year}\n".encode("utf-8")
        )

    for student in session.query(StudentModel).order_by(StudentModel.id).all():
        hasher.update(
            f"student|{student.id}|{student.name}|{student.dataset_split.value}\n".encode("utf-8")
        )

    for enrollment in session.query(EnrollmentModel).order_by(EnrollmentModel.id).all():
        hasher.update(
            f"enrollment|{enrollment.id}|{enrollment.student_id}|{enrollment.classroom_id}\n".encode(
                "utf-8"
            )
        )

    return hasher.hexdigest()
