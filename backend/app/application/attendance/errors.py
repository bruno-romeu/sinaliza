class ClassroomNotFoundError(Exception):
    """Raised by `ListEnrolledStudentsService` when the given `classroom_id`
    does not exist (spec I/O Matrix, "Unknown classroom")."""


class StudentNotEnrolledError(Exception):
    """Raised by `RegisterAttendanceService` when `student_id` is not
    enrolled in `classroom_id` — prevents attendance rows disconnected from
    a real matrícula (spec I/O Matrix, "Student not enrolled")."""


class DuplicateAttendanceError(Exception):
    """Raised by `RegisterAttendanceService` when an attendance record
    already exists for the same (student_id, classroom_id, date) —
    translated from the DB-level `UNIQUE` constraint's `IntegrityError`
    (AD-7, spec I/O Matrix "Duplicate" / "DB-level bypass")."""
