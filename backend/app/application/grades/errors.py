"""Small, intentionally duplicated from `attendance/errors.py` (spec Code
Map) to keep the two vertical slices independently importable."""


class ClassroomNotFoundError(Exception):
    """Raised by `RegisterGradeService` when the given `classroom_id` does
    not exist (spec I/O Matrix, "Unknown classroom")."""


class StudentNotEnrolledError(Exception):
    """Raised by `RegisterGradeService` when `student_id` is not enrolled in
    `classroom_id` — prevents grade rows disconnected from a real matrícula
    (spec I/O Matrix, "Student not enrolled")."""


class AcademicPeriodNotFoundError(Exception):
    """Raised by `RegisterGradeService` when the given `period_id` does not
    exist (spec I/O Matrix, "Unknown period")."""
