"""Ports (interfaces) the `application/observations` layer depends on.

`ClassroomRepositoryPort`/`StudentRepositoryPort` are reused as-is from
`application/attendance/ports.py` (spec Code Map: "import only, no
changes") — only `PedagogicalObservationRepositoryPort` is new here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from app.domain.pedagogical_observation import PedagogicalObservation


class PedagogicalObservationRepositoryPort(Protocol):
    def save(
        self,
        student_id: uuid.UUID,
        author_user_id: uuid.UUID,
        text: str,
        created_at: datetime,
    ) -> PedagogicalObservation: ...
