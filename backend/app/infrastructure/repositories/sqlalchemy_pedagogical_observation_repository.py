"""Implements `PedagogicalObservationRepositoryPort` on top of SQLAlchemy.

`save` never needs to translate an `IntegrityError` into a domain error —
`pedagogical_observations` carries no UNIQUE constraint (spec Boundaries &
Constraints: multiple observations for the same student are expected and
valid, each a new row, same precedent as `Grade`/`AssignmentSubmission`).

`list_by_student_in_range` (Story 3.2) feeds the pedagogical
`SignalEvaluator` — it filters on `created_at`'s date, mirroring
`SqlAlchemyAttendanceRepository.list_by_student_in_range`'s shape, and applies
`filter_as_of` (AD-11) as the same leak-prevention invariant every other
trajectory-facing read already carries. Story 4.4 never touches this method
— `SignalEvaluator`/`ConvergenceRule` must keep seeing the complete,
unfiltered set of observations (AD-8).

`get_by_ids` (Story 3.4) is extended by Story 4.4 with a `requesting_user_id`
read-time visibility filter (RF-22, AD-8, AD-11): the scoping rule lives
here, the only place both evidence-resolution call sites
(`GetStudentTrajectoryDetailService`, `GetFollowUpService`) share, so it is
never duplicated inline in a router or application service."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import cast, select
from sqlalchemy import Date as SA_Date
from sqlalchemy.orm import Session

from app.domain.pedagogical_observation import PedagogicalObservation
from app.domain.trajectory_change import SourceType
from app.infrastructure.db.models import (
    FollowUpEvidenceModel,
    FollowUpModel,
    PedagogicalObservationModel,
    TrajectoryChangeSourceModel,
)
from app.infrastructure.repositories.base import filter_as_of

# Story 4.4 (RF-22, AD-8): shown in place of the real text whenever an
# observation is cited as evidence of a real `FollowUp` and the requesting
# user is not that `FollowUp`'s responsible user — factual, never a vague
# "access denied" (EXPERIENCE.md Voice and Tone).
_RESTRICTED_TEXT = (
    "Texto do registro pedagógico restrito ao responsável pelo "
    "acompanhamento que o cita como evidência."
)


class SqlAlchemyPedagogicalObservationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        student_id: uuid.UUID,
        author_user_id: uuid.UUID,
        text: str,
        created_at: datetime,
        registers_concern: bool = False,
    ) -> PedagogicalObservation:
        model = PedagogicalObservationModel(
            student_id=student_id,
            author_user_id=author_user_id,
            text=text,
            created_at=created_at,
            registers_concern=registers_concern,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return PedagogicalObservation(
            id=model.id,
            student_id=model.student_id,
            author_user_id=model.author_user_id,
            text=model.text,
            created_at=model.created_at,
            registers_concern=model.registers_concern,
        )

    def list_by_student_in_range(
        self, student_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[PedagogicalObservation]:
        created_at_date = cast(PedagogicalObservationModel.created_at, SA_Date)
        stmt = select(PedagogicalObservationModel).where(
            PedagogicalObservationModel.student_id == student_id,
            created_at_date >= start_date,
            created_at_date <= end_date,
        )
        stmt = filter_as_of(stmt, created_at_date)
        models = self._session.execute(stmt).scalars().all()
        return [
            PedagogicalObservation(
                id=model.id,
                student_id=model.student_id,
                author_user_id=model.author_user_id,
                text=model.text,
                created_at=model.created_at,
                registers_concern=model.registers_concern,
            )
            for model in models
        ]

    def get_by_ids(
        self, ids: list[uuid.UUID], requesting_user_id: uuid.UUID
    ) -> list[PedagogicalObservation]:
        """Story 3.4 — batch resolution of `TrajectoryChangeSource.source_id`
        rows for the evidence card (RNF-11). Story 4.4 — scopes `text`
        visibility: an observation cited as evidence of a real `FollowUp`
        (`TrajectoryChangeSource` → `TrajectoryChange` → `FollowUpEvidence`)
        is redacted unless `requesting_user_id` is the `responsible_user_id`
        of at least one `FollowUp` citing it (RF-22, AD-8)."""
        if not ids:
            return []
        created_at_date = cast(PedagogicalObservationModel.created_at, SA_Date)
        stmt = select(PedagogicalObservationModel).where(PedagogicalObservationModel.id.in_(ids))
        stmt = filter_as_of(stmt, created_at_date)
        models = self._session.execute(stmt).scalars().all()

        restricted_ids = self._restricted_ids(ids)
        visible_ids = (
            self._visible_to_user_ids(ids, requesting_user_id) if restricted_ids else set()
        )

        return [
            PedagogicalObservation(
                id=model.id,
                student_id=model.student_id,
                author_user_id=model.author_user_id,
                text=(
                    _RESTRICTED_TEXT
                    if model.id in restricted_ids and model.id not in visible_ids
                    else model.text
                ),
                created_at=model.created_at,
                registers_concern=model.registers_concern,
            )
            for model in models
        ]

    def _restricted_ids(self, ids: list[uuid.UUID]) -> set[uuid.UUID]:
        """Every id in `ids` cited (via `TrajectoryChangeSource`) by a
        `TrajectoryChange` that has at least one real `FollowUpEvidence` row
        — i.e. actually cited as evidence of some `FollowUp` (RF-22)."""
        stmt = (
            select(TrajectoryChangeSourceModel.source_id)
            .distinct()
            .join(
                FollowUpEvidenceModel,
                FollowUpEvidenceModel.trajectory_change_id
                == TrajectoryChangeSourceModel.trajectory_change_id,
            )
            .where(
                TrajectoryChangeSourceModel.source_type == SourceType.PEDAGOGICAL_OBSERVATION,
                TrajectoryChangeSourceModel.source_id.in_(ids),
            )
        )
        return set(self._session.execute(stmt).scalars().all())

    def _visible_to_user_ids(
        self, ids: list[uuid.UUID], requesting_user_id: uuid.UUID
    ) -> set[uuid.UUID]:
        """Subset of `_restricted_ids(ids)` where `requesting_user_id` is the
        `responsible_user_id` of at least one citing `FollowUp` — a
        restricted observation cited by several `FollowUp`s is visible to
        any of their responsible users, never only one (AD-8)."""
        stmt = (
            select(TrajectoryChangeSourceModel.source_id)
            .distinct()
            .join(
                FollowUpEvidenceModel,
                FollowUpEvidenceModel.trajectory_change_id
                == TrajectoryChangeSourceModel.trajectory_change_id,
            )
            .join(FollowUpModel, FollowUpModel.id == FollowUpEvidenceModel.follow_up_id)
            .where(
                TrajectoryChangeSourceModel.source_type == SourceType.PEDAGOGICAL_OBSERVATION,
                TrajectoryChangeSourceModel.source_id.in_(ids),
                FollowUpModel.responsible_user_id == requesting_user_id,
            )
        )
        return set(self._session.execute(stmt).scalars().all())
