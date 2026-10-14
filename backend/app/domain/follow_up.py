"""Domain model for `FollowUp`/`FollowUpEvidence` — pure Python, zero
framework imports (AD-2). Mirrors `domain/trajectory_change.py`'s style.

`FollowUpStatus` is a closed, 4-value enum (spec Boundaries & Constraints,
AD-6): `EM_OBSERVACAO` is the only status this story ever writes — the other
three (`ACOMPANHAMENTO_ATIVO`, `AGUARDANDO_RETORNO`, `ENCERRADO`) exist only so
the native Postgres enum and the frontend's status pill are already complete
for Stories 4.2+'s transitions, never implemented here (spec Never).

`FollowUp.reason`/`next_review_date` are always `NULL` in this story — no UI
captures them yet (spec Boundaries & Constraints, Design Notes).

`FollowUpEvidence.trajectory_change_id` is a real `NOT NULL` FK (RNF-11,
AD-7) — unlike `TrajectoryChangeSource.source_id`, which is necessarily
polymorphic, a `FollowUpEvidence` row always points at exactly one
`TrajectoryChange` row, so it can be a real FK without any polymorphism.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class FollowUpStatus(str, Enum):
    EM_OBSERVACAO = "EM_OBSERVACAO"
    ACOMPANHAMENTO_ATIVO = "ACOMPANHAMENTO_ATIVO"
    AGUARDANDO_RETORNO = "AGUARDANDO_RETORNO"
    ENCERRADO = "ENCERRADO"


@dataclass(frozen=True)
class FollowUp:
    id: uuid.UUID
    student_id: uuid.UUID
    status: FollowUpStatus
    reason: str | None
    responsible_user_id: uuid.UUID
    next_review_date: date | None
    created_at: datetime


@dataclass(frozen=True)
class FollowUpEvidence:
    id: uuid.UUID
    follow_up_id: uuid.UUID
    trajectory_change_id: uuid.UUID


@dataclass(frozen=True)
class FollowUpAction:
    """A free-text action registered against an open `FollowUp` (RF-13,
    RF-14). Always a fresh INSERT — never updated or replaced — so the
    history accumulates one row per submission (spec Boundaries &
    Constraints)."""

    id: uuid.UUID
    follow_up_id: uuid.UUID
    description: str
    author_user_id: uuid.UUID
    created_at: datetime
