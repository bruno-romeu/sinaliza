"""Implements `PedagogicalObservationRepositoryPort` on top of SQLAlchemy.

`save` carries no UNIQUE constraint (spec Boundaries & Constraints: multiple
observations for the same student are expected and valid, each a new row,
same precedent as `Grade`/`AssignmentSubmission`), so no *duplicate* can be
raised here — but its two FKs (`student_id`, `author_user_id`) can still be
violated, and that used to escape as a raw `IntegrityError` with the session
left unusable. It now goes through `translating_integrity_errors`, like every
other write path in `infrastructure/repositories` (see
`repositories/errors.py`).

`list_by_student_in_range` (Story 3.2) feeds the pedagogical
`SignalEvaluator` — it buckets `created_at` into its **UTC** calendar date
(`base.utc_date_of`, never a bare `::date` resolved at the session's
`timezone` GUC), mirroring
`SqlAlchemyAttendanceRepository.list_by_student_in_range`'s shape, and applies
`filter_as_of` (AD-11) as the same leak-prevention invariant every other
trajectory-facing read already carries. Story 4.4 never touches this method
— `SignalEvaluator`/`ConvergenceRule` must keep seeing the complete,
unfiltered set of observations (AD-8).

`get_by_ids` (Story 3.4) is extended by Story 4.4 with a `requesting_user_id`
read-time visibility filter (RF-22, AD-8, AD-11): the scoping rule lives
here, the only place both evidence-resolution call sites
(`GetStudentTrajectoryDetailService`, `GetFollowUpService`) share, so it is
never duplicated inline in a router or application service. Its
restricted/visible lookup is a single grouped query (not the two near-
identical ones it used to run), so resolving evidence costs 2 round trips
instead of 3."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.pedagogical_observation import PedagogicalObservation
from app.domain.trajectory_change import SourceType
from app.infrastructure.db.models import (
    FollowUpEvidenceModel,
    FollowUpModel,
    PedagogicalObservationModel,
    TrajectoryChangeSourceModel,
)
from app.infrastructure.repositories.base import filter_as_of_timestamp, utc_date_of
from app.infrastructure.repositories.errors import translating_integrity_errors

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
        with translating_integrity_errors(self._session):
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
        created_at_date = utc_date_of(PedagogicalObservationModel.created_at)
        stmt = select(PedagogicalObservationModel).where(
            PedagogicalObservationModel.student_id == student_id,
            created_at_date >= start_date,
            created_at_date <= end_date,
        )
        stmt = filter_as_of_timestamp(stmt, PedagogicalObservationModel.created_at)
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
        stmt = select(PedagogicalObservationModel).where(PedagogicalObservationModel.id.in_(ids))
        stmt = filter_as_of_timestamp(stmt, PedagogicalObservationModel.created_at)
        models = self._session.execute(stmt).scalars().all()

        restricted_ids, visible_ids = self._visibility(ids, requesting_user_id)

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

    def _visibility(
        self, ids: list[uuid.UUID], requesting_user_id: uuid.UUID
    ) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
        """`(restricted_ids, visible_ids)` in one round trip.

        `restricted_ids`: every id in `ids` cited (via
        `TrajectoryChangeSource`) by a `TrajectoryChange` that has at least
        one real `FollowUpEvidence` row — i.e. actually cited as evidence of
        some `FollowUp` (RF-22).

        `visible_ids`: the subset of those where `requesting_user_id` is the
        `responsible_user_id` of at least one citing `FollowUp` — a
        restricted observation cited by several `FollowUp`s is visible to any
        of their responsible users, never only one (AD-8). That is exactly
        `bool_or(responsible_user_id = :requesting_user_id)` over the same
        grouped rows.

        This used to be two near-identical queries (`_restricted_ids` then
        `_visible_to_user_ids`), differing only by the extra join to
        `follow_ups` and the `responsible_user_id` predicate. The join to
        `follow_ups` is lossless here — `FollowUpEvidence.follow_up_id` is a
        `NOT NULL` FK — so grouping once answers both questions and drops one
        round trip per evidence resolution.
        """
        visible = func.bool_or(FollowUpModel.responsible_user_id == requesting_user_id)
        stmt = (
            select(TrajectoryChangeSourceModel.source_id, visible)
            .join(
                FollowUpEvidenceModel,
                FollowUpEvidenceModel.trajectory_change_id
                == TrajectoryChangeSourceModel.trajectory_change_id,
            )
            .join(FollowUpModel, FollowUpModel.id == FollowUpEvidenceModel.follow_up_id)
            .where(
                TrajectoryChangeSourceModel.source_type == SourceType.PEDAGOGICAL_OBSERVATION,
                TrajectoryChangeSourceModel.source_id.in_(ids),
            )
            .group_by(TrajectoryChangeSourceModel.source_id)
        )
        restricted_ids: set[uuid.UUID] = set()
        visible_ids: set[uuid.UUID] = set()
        for source_id, is_visible in self._session.execute(stmt).all():
            restricted_ids.add(source_id)
            if is_visible:
                visible_ids.add(source_id)
        return restricted_ids, visible_ids
