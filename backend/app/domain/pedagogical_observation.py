"""Domain model for `PedagogicalObservation` — pure Python, zero framework
imports (AD-2).

No `follow_up_id`/FK to `FollowUp`/`TrajectoryChange` here (data-model.md:
it belongs to the student, not to a follow-up). No visibility-scoping field
either — AD-8's read-time filter is a future concern layered on by Epic 4
(Story 4.4), never persisted on this shape.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PedagogicalObservation:
    id: uuid.UUID
    student_id: uuid.UUID
    author_user_id: uuid.UUID
    text: str
    created_at: datetime
