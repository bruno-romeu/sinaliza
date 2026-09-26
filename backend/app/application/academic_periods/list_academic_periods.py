"""`ListAcademicPeriodsService` — lists every dev-fixture academic period.

There is no academic-period registration screen (spec Boundaries &
Constraints); periods only ever come from `seed_dev_fixtures.py`.
"""

from __future__ import annotations

from app.application.academic_periods.ports import AcademicPeriodRepositoryPort
from app.domain.academic_period import AcademicPeriod


class ListAcademicPeriodsService:
    def __init__(self, academic_period_repository: AcademicPeriodRepositoryPort) -> None:
        self._academic_period_repository = academic_period_repository

    def execute(self) -> list[AcademicPeriod]:
        return self._academic_period_repository.list_all()
