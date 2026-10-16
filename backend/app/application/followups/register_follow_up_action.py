"""`RegisterFollowUpActionService` — the one and only path that writes a
`FollowUpAction` (spec Boundaries & Constraints: "the router only ever calls
this service, never a router-level field assignment").

`author_user_id` is always the caller-supplied authenticated user, never a
request field — the router is responsible for sourcing it from
`get_current_user`, never this service (mirrors `OpenFollowUpService`'s
`responsible_user_id` idiom). Action submission is never gated on the
follow-up's current status (spec Never) — any of the 4 statuses accepts a
new action.

`author_user_id` also doubles as `requesting_user_id`: this service scopes
registration to the `FollowUp`'s `responsible_user_id` (RF-22 write-side,
epic-4-retro-item-18), the same trust boundary Story 4.4 already applies to
reads.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.application.followups.errors import FollowUpAccessDeniedError, FollowUpNotFoundError
from app.application.followups.ports import FollowUpRepositoryPort
from app.domain.follow_up import FollowUpAction


class RegisterFollowUpActionService:
    def __init__(self, follow_up_repository: FollowUpRepositoryPort) -> None:
        self._follow_up_repository = follow_up_repository

    def execute(
        self,
        follow_up_id: uuid.UUID,
        description: str,
        author_user_id: uuid.UUID,
    ) -> FollowUpAction:
        follow_up = self._follow_up_repository.get_by_id(follow_up_id)
        if follow_up is None:
            raise FollowUpNotFoundError()
        if follow_up.responsible_user_id != author_user_id:
            raise FollowUpAccessDeniedError()

        action = FollowUpAction(
            id=uuid.uuid4(),
            follow_up_id=follow_up_id,
            description=description,
            author_user_id=author_user_id,
            created_at=datetime.now(UTC),
        )
        return self._follow_up_repository.add_action(action)
