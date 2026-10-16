"""`ChangeFollowUpStatusService` — the one and only place that ever changes
`FollowUp.status` (AD-6, spec Boundaries & Constraints). The router/
repository never assign `FollowUpModel.status` directly outside this
service's single call into `update_status`.

No adjacency rules: all 4 `FollowUpStatus` values are always a valid target
regardless of the current status (spec Never) — there is no state-machine
here, just a plain column update.

`requesting_user_id` scopes the mutation to the `FollowUp`'s
`responsible_user_id` (RF-22 write-side, epic-4-retro-item-18) — the same
trust boundary Story 4.4 already applies to reads.
"""

from __future__ import annotations

import uuid

from app.application.followups.errors import FollowUpAccessDeniedError, FollowUpNotFoundError
from app.application.followups.ports import FollowUpRepositoryPort
from app.domain.follow_up import FollowUp, FollowUpStatus


class ChangeFollowUpStatusService:
    def __init__(self, follow_up_repository: FollowUpRepositoryPort) -> None:
        self._follow_up_repository = follow_up_repository

    def execute(
        self, follow_up_id: uuid.UUID, status: FollowUpStatus, requesting_user_id: uuid.UUID
    ) -> FollowUp:
        follow_up = self._follow_up_repository.get_by_id(follow_up_id)
        if follow_up is None:
            raise FollowUpNotFoundError()
        if follow_up.responsible_user_id != requesting_user_id:
            raise FollowUpAccessDeniedError()

        updated = self._follow_up_repository.update_status(follow_up_id, status)
        if updated is None:
            raise FollowUpNotFoundError()
        return updated
