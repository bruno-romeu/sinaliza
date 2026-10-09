from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class TrajectoryChangeOut(BaseModel):
    type: Literal[
        "ATTENDANCE_DROP",
        "GRADE_DROP",
        "MISSING_ASSIGNMENTS_INCREASE",
        "COMBINED_DETERIORATION",
    ]
    period_id: uuid.UUID
    detected_at: datetime
    description: str


class ConcerningFactorOut(BaseModel):
    kind: Literal["ATTENDANCE", "GRADE", "ASSIGNMENTS", "PEDAGOGICAL_OBSERVATION"]
    description: str


class TrajectoryOut(BaseModel):
    # Exactly the 6 indicators the spec requires, plus Story 3.2's
    # convergence output — never `synthetic_profile` (spec Boundaries &
    # Constraints: "synthetic_profile nunca na resposta") and never
    # `source_ids` (no stable id for a `concerning_factor`, RNF-11 evidence
    # lives only behind `TrajectoryChangeSource`, not in this response).
    #
    # `missing_assignments_count`/`missing_assignment_delta` and the
    # `ASSIGNMENTS` signal behind `concerning_factor`/`trajectory_change` can
    # legitimately disagree for the same student/period: the former counts
    # every due assignment with no `DELIVERED` submission, while the latter
    # counts only assignments with a citable registered
    # `NOT_DELIVERED`/`PARTIAL` submission (domain/convergence.py's stricter,
    # citability-driven cut).
    attendance_rate: Decimal | None
    attendance_trend: Decimal | None
    grade_average: Decimal | None
    grade_trend: Decimal | None
    missing_assignments_count: int
    missing_assignment_delta: int
    trajectory_change: TrajectoryChangeOut | None
    concerning_factor: ConcerningFactorOut | None
