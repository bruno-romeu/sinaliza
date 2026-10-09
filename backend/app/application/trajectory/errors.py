class StudentNotFoundError(Exception):
    """Raised by `GetStudentTrajectoryService` when `student_id` doesn't
    exist, or exists but is `TRAIN`-split — both map to the exact same 404
    (spec I/O Matrix: "Estudante inexistente/TRAIN... 404 student_not_found
    idêntico nos dois casos"), so the split is never observable from the
    response."""
