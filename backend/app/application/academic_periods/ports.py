"""Ports (interfaces) the `application/academic_periods` layer depends on.

`application/` only ever sees these Protocols — never a concrete class from
`infrastructure/` (AD-2). Concrete adapters are wired up in `composition.py`
(the composition root) and injected here.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from app.domain.academic_period import AcademicPeriod


class AcademicPeriodRepositoryPort(Protocol):
    def list_all(self) -> list[AcademicPeriod]: ...

    def get_by_id(self, period_id: uuid.UUID) -> AcademicPeriod | None: ...
