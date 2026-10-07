"""Content fingerprint of the generated population — SHA-256 over a declared,
stably-ordered column list (Design Notes: "Fingerprint excludes
`executed_at`"). This, not row counts, is what RNF-13's determinism claim is
proven by: two generations of the same seed must hash identical, and two
generations of different seeds must hash different.

Extended (not rewritten) by later stories: Story 2.2/2.3/2.5 append their own
generated tables to the same declaration rather than replacing it. Story 2.2
extends it to cover `students.synthetic_profile` (now non-NULL) and the four
fact tables it populates — `grades`/`assignments` hash each row's period by
`AcademicPeriod.order_index`, never `period_id` (a random `uuid.uuid4()`
assigned by `seed_dev_fixtures.py`, not derived from the generator's seed;
Design Notes).
"""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    AcademicPeriodModel,
    AssignmentModel,
    AssignmentSubmissionModel,
    AttendanceRecordModel,
    ClassroomModel,
    EnrollmentModel,
    GradeModel,
    StudentModel,
)


def population_fingerprint(session: Session) -> str:
    """SHA-256 hex digest over `classrooms`, `students` (incl.
    `synthetic_profile`), `enrollments`, `attendance_records`, `grades`,
    `assignments` and `assignment_submissions`, each read back in a stable
    `ORDER BY id` and a declared column list. Deliberately excludes
    `synthetic_generation_runs.executed_at` (wall-clock, never
    reproducible)."""
    hasher = hashlib.sha256()

    for classroom in session.query(ClassroomModel).order_by(ClassroomModel.id).all():
        hasher.update(
            f"classroom|{classroom.id}|{classroom.name}|{classroom.academic_year}\n".encode("utf-8")
        )

    for student in session.query(StudentModel).order_by(StudentModel.id).all():
        profile_label = student.synthetic_profile.value if student.synthetic_profile else "NULL"
        hasher.update(
            f"student|{student.id}|{student.name}|{student.dataset_split.value}|"
            f"{profile_label}\n".encode("utf-8")
        )

    for enrollment in session.query(EnrollmentModel).order_by(EnrollmentModel.id).all():
        hasher.update(
            f"enrollment|{enrollment.id}|{enrollment.student_id}|{enrollment.classroom_id}\n".encode(
                "utf-8"
            )
        )

    for record in session.query(AttendanceRecordModel).order_by(AttendanceRecordModel.id).all():
        hasher.update(
            f"attendance|{record.id}|{record.student_id}|{record.classroom_id}|"
            f"{record.date}|{record.status.value}\n".encode("utf-8")
        )

    grade_rows = (
        session.query(GradeModel, AcademicPeriodModel.order_index)
        .join(AcademicPeriodModel, GradeModel.period_id == AcademicPeriodModel.id)
        .order_by(GradeModel.id)
        .all()
    )
    for grade, order_index in grade_rows:
        hasher.update(
            f"grade|{grade.id}|{grade.student_id}|{grade.classroom_id}|{grade.subject}|"
            f"{order_index}|{grade.date}|{grade.value}\n".encode("utf-8")
        )

    assignment_rows = (
        session.query(AssignmentModel, AcademicPeriodModel.order_index)
        .join(AcademicPeriodModel, AssignmentModel.period_id == AcademicPeriodModel.id)
        .order_by(AssignmentModel.id)
        .all()
    )
    for assignment, order_index in assignment_rows:
        hasher.update(
            f"assignment|{assignment.id}|{assignment.classroom_id}|{assignment.subject}|"
            f"{order_index}|{assignment.due_date}\n".encode("utf-8")
        )

    for submission in (
        session.query(AssignmentSubmissionModel).order_by(AssignmentSubmissionModel.id).all()
    ):
        hasher.update(
            f"assignment_submission|{submission.id}|{submission.assignment_id}|"
            f"{submission.student_id}|{submission.status.value}|"
            f"{submission.date}\n".encode("utf-8")
        )

    return hasher.hexdigest()
