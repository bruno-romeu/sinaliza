"""Small, intentionally duplicated from `attendance/errors.py`/
`grades/errors.py` (spec Code Map) to keep the vertical slices independently
importable."""


class ClassroomNotFoundError(Exception):
    """Raised by `RegisterAssignmentService`/`ListAssignmentsByClassroomService`
    when the given `classroom_id` does not exist (spec I/O Matrix, "Unknown
    classroom")."""


class AcademicPeriodNotFoundError(Exception):
    """Raised by `RegisterAssignmentService` when the given `period_id` does
    not exist (spec I/O Matrix, "Unknown period")."""


class AssignmentNotFoundError(Exception):
    """Raised by `RegisterSubmissionService` when the given `assignment_id`
    does not exist (spec I/O Matrix, "Unknown assignment")."""


class StudentNotEnrolledError(Exception):
    """Raised by `RegisterSubmissionService` when `student_id` is not
    enrolled in the assignment's classroom (spec I/O Matrix, "Student not
    enrolled")."""
