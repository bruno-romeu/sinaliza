"""Small, intentionally duplicated from `observations/errors.py`/
`attendance/errors.py` (spec Code Map) to keep this vertical slice
independently importable."""


class TrajectoryChangeNotFoundError(Exception):
    """Raised by `OpenFollowUpService` when the payload's
    `trajectory_change_id` does not reference an existing `TrajectoryChange`
    (spec I/O Matrix, "Unknown trajectory_change_id")."""


class TrajectoryChangeMismatchError(Exception):
    """Raised by `OpenFollowUpService` when the referenced
    `TrajectoryChange.student_id` does not match the payload's `student_id`
    (spec I/O Matrix, "student_id/trajectory_change mismatch")."""


class FollowUpNotFoundError(Exception):
    """Raised by `GetFollowUpService` when the given `follow_up_id` does not
    exist (spec I/O Matrix, "Nonexistent follow-up")."""
