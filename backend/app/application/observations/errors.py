"""Small, intentionally duplicated from `attendance/errors.py`/`grades/errors.py`
(spec Code Map) to keep this vertical slice independently importable."""


class ClassroomNotFoundError(Exception):
    """Raised by `RegisterObservationService` when the given `classroom_id`
    does not exist (spec I/O Matrix, "Unknown classroom")."""


class StudentNotEnrolledError(Exception):
    """Raised by `RegisterObservationService` when `student_id` is not
    enrolled in `classroom_id` (spec I/O Matrix, "Student not enrolled")."""
