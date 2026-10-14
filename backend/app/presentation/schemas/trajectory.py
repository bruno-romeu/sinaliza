from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class TrajectoryChangeOut(BaseModel):
    # Story 4.1: additive `id` field so the frontend can submit
    # `trajectory_change_id` to `POST /follow-ups` — the rest of this shape
    # (and both /trajectory and /trajectory/detail response contracts) is
    # otherwise untouched (spec Boundaries & Constraints).
    id: uuid.UUID
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
    missing_assignments_count: int = Field(
        description=(
            "Total due assignments with no DELIVERED submission. Can legitimately "
            "disagree with the ASSIGNMENTS signal behind trajectory_change/"
            "concerning_factor, which counts only assignments with a citable "
            "registered NOT_DELIVERED/PARTIAL submission."
        )
    )
    missing_assignment_delta: int = Field(
        description=(
            "Change in missing_assignments_count vs. the previous period. Subject "
            "to the same ASSIGNMENTS-signal divergence as missing_assignments_count."
        )
    )
    trajectory_change: TrajectoryChangeOut | None
    concerning_factor: ConcerningFactorOut | None


# --- Story 3.4: GET /students/{id}/trajectory/detail ------------------------


class TrajectorySeriesPointOut(BaseModel):
    period_id: uuid.UUID
    period_label: str
    value: Decimal | None


class HabitualRangeOut(BaseModel):
    low: Decimal
    high: Decimal


class EvidenceItemOut(BaseModel):
    source_type: Literal[
        "ATTENDANCE_RECORD", "GRADE", "ASSIGNMENT_SUBMISSION", "PEDAGOGICAL_OBSERVATION"
    ]
    description: str
    date: date


class ObservationItemOut(BaseModel):
    date: date
    text: str


class TrajectoryDetailOut(BaseModel):
    # `chart_indicator` is chosen deterministically from `trajectory_change`'s
    # `type` (spec Boundaries & Constraints), defaulting to `attendance_rate`
    # absent a change.
    chart_indicator: Literal["attendance_rate", "grade_average", "missing_assignments_count"]
    series: list[TrajectorySeriesPointOut]
    habitual_range: HabitualRangeOut | None
    trajectory_change: TrajectoryChangeOut | None
    evidence: list[EvidenceItemOut]
    concerning_factor: ConcerningFactorOut | None
    observations: list[ObservationItemOut]
