from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class TrajectoryOut(BaseModel):
    # Exactly the 6 indicators the spec requires, nothing else — in
    # particular, never `synthetic_profile` (spec Boundaries & Constraints:
    # "synthetic_profile nunca na resposta").
    attendance_rate: Decimal | None
    attendance_trend: Decimal | None
    grade_average: Decimal | None
    grade_trend: Decimal | None
    missing_assignments_count: int
    missing_assignment_delta: int
