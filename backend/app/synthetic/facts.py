"""Pure construction of one synthetic population's observable facts (Story
2.2) — attendance, grades, assignments, assignment submissions.

Zero I/O, zero SQLAlchemy imports (AD-2's spirit, `population.py`'s
precedent): this module never imports `AcademicPeriodModel`. The caller
(`generate.py`) is the only place that touches the ORM, converting queried
`AcademicPeriodModel` rows into `PeriodWindow` before calling into this
module.

Every id, date, status and value is derived only from
`(config.seed, student_id, ...)` via `app.synthetic.profiles`/`rng` — never
ambient randomness — so `build_facts` called twice with the same inputs
always returns the same output, byte for byte.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.domain.assignment_submission import AssignmentSubmissionStatus
from app.domain.attendance import AttendanceStatus
from app.domain.student import SyntheticProfile
from app.synthetic import profiles
from app.synthetic.population import GeneratedPopulation, GenerationConfig
from app.synthetic.rng import derived_key, stable_uuid

#: Fixed 4-item tuple, not calibrated data (Assumption 1) — no AC specifies
#: subject names or count. 4 keeps full-volume row counts (~3,200 grades,
#: ~128 assignments, ~3,200 submissions) proportionate to the ~40k
#: attendance rows the epic plan already budgets for.
SUBJECTS: tuple[str, ...] = ("Matemática", "Português", "Ciências", "História")


@dataclass(frozen=True)
class PeriodWindow:
    """A plain stand-in for `AcademicPeriodModel`, so this module never needs
    the ORM (Design Notes). `id_label` is built from `order_index` — stable
    and seed-independent, unlike `AcademicPeriodModel.id` (a random
    `uuid.uuid4()` assigned by `seed_dev_fixtures.py`)."""

    id_label: str
    start_date: date
    end_date: date
    order_index: int


def school_days(periods: tuple[PeriodWindow, ...]) -> tuple[date, ...]:
    """One school day per weekday inside each period's `[start_date,
    end_date]`, excluding gaps between periods — built strictly per period,
    never over the full year span (spec Boundaries & Constraints).

    Sorted and deduplicated: overlapping period date ranges (a data issue
    this module does not own, but must not silently misbehave under) would
    otherwise emit the same date twice, which the per-student attendance
    loop would turn into two `AttendanceRecord` rows for the same
    `(student_id, classroom_id, date)` — the exact collision the DB `UNIQUE`
    constraint exists to forbid."""
    days: set[date] = set()
    for period in periods:
        current = period.start_date
        while current <= period.end_date:
            if current.weekday() < 5:  # Monday=0 .. Friday=4
                days.add(current)
            current += timedelta(days=1)
    return tuple(sorted(days))


@dataclass(frozen=True)
class GeneratedAttendanceRecord:
    id: uuid.UUID
    student_id: uuid.UUID
    classroom_id: uuid.UUID
    date: date
    status: AttendanceStatus


@dataclass(frozen=True)
class GeneratedGrade:
    id: uuid.UUID
    student_id: uuid.UUID
    classroom_id: uuid.UUID
    subject: str
    period_order_index: int
    date: date
    value: Decimal


@dataclass(frozen=True)
class GeneratedAssignment:
    id: uuid.UUID
    classroom_id: uuid.UUID
    subject: str
    period_order_index: int
    due_date: date


@dataclass(frozen=True)
class GeneratedAssignmentSubmission:
    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    status: AssignmentSubmissionStatus
    date: date


@dataclass(frozen=True)
class GeneratedFacts:
    attendance_records: tuple[GeneratedAttendanceRecord, ...]
    grades: tuple[GeneratedGrade, ...]
    assignments: tuple[GeneratedAssignment, ...]
    assignment_submissions: tuple[GeneratedAssignmentSubmission, ...]


def _justification_is_justified(seed: int, student_id: uuid.UUID, day: date) -> bool:
    """A fresh, undocumented 50/50 coin (Assumption 4) on every non-present
    day, independent of profile — `calibration.py`/`research.md` have no
    public source for this split either, and RF-11 counts both equally."""
    fraction = derived_key(seed, "attendance_justification", str(student_id), day.isoformat())
    return fraction % 2 == 0


def _build_attendance(
    population: GeneratedPopulation,
    classroom_by_student: dict[uuid.UUID, uuid.UUID],
    days: tuple[date, ...],
    seed: int,
) -> tuple[GeneratedAttendanceRecord, ...]:
    total_days = len(days)
    records: list[GeneratedAttendanceRecord] = []

    for student in population.students:
        classroom_id = classroom_by_student[student.id]
        for day_index, day in enumerate(days):
            present = profiles.attendance_is_present(
                seed, student.id, student.synthetic_profile, day_index, total_days
            )
            if present:
                status = AttendanceStatus.PRESENT
            elif _justification_is_justified(seed, student.id, day):
                status = AttendanceStatus.ABSENT_JUSTIFIED
            else:
                status = AttendanceStatus.ABSENT_UNJUSTIFIED

            records.append(
                GeneratedAttendanceRecord(
                    id=stable_uuid(seed, "attendance", str(student.id), day.isoformat()),
                    student_id=student.id,
                    classroom_id=classroom_id,
                    date=day,
                    status=status,
                )
            )

    return tuple(records)


def _build_grades(
    population: GeneratedPopulation,
    classroom_by_student: dict[uuid.UUID, uuid.UUID],
    periods: tuple[PeriodWindow, ...],
    seed: int,
) -> tuple[GeneratedGrade, ...]:
    total_periods = len(periods)
    grades: list[GeneratedGrade] = []

    for student in population.students:
        classroom_id = classroom_by_student[student.id]
        for period_index, period in enumerate(periods):
            for subject in SUBJECTS:
                value = profiles.grade_value(
                    seed,
                    student.id,
                    period.id_label,
                    subject,
                    student.synthetic_profile,
                    period_index,
                    total_periods,
                )
                grades.append(
                    GeneratedGrade(
                        id=stable_uuid(seed, "grade", str(student.id), period.id_label, subject),
                        student_id=student.id,
                        classroom_id=classroom_id,
                        subject=subject,
                        period_order_index=period.order_index,
                        date=period.end_date,
                        value=value,
                    )
                )

    return tuple(grades)


def _build_assignments(
    population: GeneratedPopulation,
    periods: tuple[PeriodWindow, ...],
    seed: int,
) -> tuple[GeneratedAssignment, ...]:
    assignments: list[GeneratedAssignment] = []

    for classroom in population.classrooms:
        for period in periods:
            for subject in SUBJECTS:
                assignments.append(
                    GeneratedAssignment(
                        id=stable_uuid(
                            seed, "assignment", str(classroom.id), period.id_label, subject
                        ),
                        classroom_id=classroom.id,
                        subject=subject,
                        period_order_index=period.order_index,
                        due_date=period.end_date,
                    )
                )

    return tuple(assignments)


def _build_assignment_submissions(
    population: GeneratedPopulation,
    assignments: tuple[GeneratedAssignment, ...],
    students_by_classroom: dict[uuid.UUID, tuple[uuid.UUID, ...]],
    profile_by_student: dict[uuid.UUID, SyntheticProfile],
    period_index_by_order: dict[int, int],
    total_periods: int,
    seed: int,
) -> tuple[GeneratedAssignmentSubmission, ...]:
    submissions: list[GeneratedAssignmentSubmission] = []

    for assignment in assignments:
        period_index = period_index_by_order[assignment.period_order_index]
        for student_id in students_by_classroom.get(assignment.classroom_id, ()):
            status = profiles.assignment_submission_status(
                seed,
                student_id,
                str(assignment.id),
                profile_by_student[student_id],
                period_index,
                total_periods,
            )
            submissions.append(
                GeneratedAssignmentSubmission(
                    id=stable_uuid(seed, "assignment_submission", str(student_id), str(assignment.id)),
                    assignment_id=assignment.id,
                    student_id=student_id,
                    status=status,
                    date=assignment.due_date,
                )
            )

    return tuple(submissions)


def build_facts(
    population: GeneratedPopulation,
    periods: tuple[PeriodWindow, ...],
    config: GenerationConfig,
) -> GeneratedFacts:
    """Deterministically build every observable fact for `population` over
    `periods`. Each student is assumed enrolled in exactly one classroom
    (Story 2.1's population-construction guarantee)."""
    seed = config.seed

    classroom_by_student: dict[uuid.UUID, uuid.UUID] = {
        enrollment.student_id: enrollment.classroom_id for enrollment in population.enrollments
    }
    students_by_classroom: dict[uuid.UUID, tuple[uuid.UUID, ...]] = {}
    for classroom in population.classrooms:
        students_by_classroom[classroom.id] = tuple(
            student_id
            for student_id, classroom_id in classroom_by_student.items()
            if classroom_id == classroom.id
        )
    profile_by_student = {student.id: student.synthetic_profile for student in population.students}
    period_index_by_order = {period.order_index: index for index, period in enumerate(periods)}

    days = school_days(periods)
    attendance_records = _build_attendance(population, classroom_by_student, days, seed)
    grades = _build_grades(population, classroom_by_student, periods, seed)
    assignments = _build_assignments(population, periods, seed)
    assignment_submissions = _build_assignment_submissions(
        population,
        assignments,
        students_by_classroom,
        profile_by_student,
        period_index_by_order,
        total_periods=len(periods),
        seed=seed,
    )

    return GeneratedFacts(
        attendance_records=attendance_records,
        grades=grades,
        assignments=assignments,
        assignment_submissions=assignment_submissions,
    )
