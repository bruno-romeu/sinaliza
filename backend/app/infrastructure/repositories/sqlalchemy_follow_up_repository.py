"""Implements `FollowUpRepositoryPort` on top of SQLAlchemy. Plain inserts
only (no upsert needed, spec Code Map). A new `FollowUp` is always a fresh row;
never updated by this repository (status transitions are Story 4.2+ scope,
spec Never: "the router never mutates `FollowUp` state directly")."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.follow_up import FollowUp, FollowUpAction, FollowUpEvidence, FollowUpStatus
from app.infrastructure.db.models import (
    FollowUpActionModel,
    FollowUpEvidenceModel,
    FollowUpModel,
    TrajectoryChangeModel,
)


class SqlAlchemyFollowUpRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_with_evidence(
        self, follow_up: FollowUp, evidence: list[FollowUpEvidence]
    ) -> FollowUp:
        self._session.add(
            FollowUpModel(
                id=follow_up.id,
                student_id=follow_up.student_id,
                status=follow_up.status,
                reason=follow_up.reason,
                responsible_user_id=follow_up.responsible_user_id,
                next_review_date=follow_up.next_review_date,
                created_at=follow_up.created_at,
            )
        )
        # Flushed before the evidence rows below: `FollowUpModel`/
        # `FollowUpEvidenceModel` have no `relationship()` between them (plain
        # FK columns only, same as `TrajectoryChangeModel`/
        # `TrajectoryChangeSourceModel`), so the unit of work has no
        # dependency edge to order these two inserts by — an explicit flush
        # here guarantees `follow_ups` is written first, inside the same
        # transaction as the evidence insert and the final commit below.
        self._session.flush()
        for item in evidence:
            self._session.add(
                FollowUpEvidenceModel(
                    id=item.id,
                    follow_up_id=item.follow_up_id,
                    trajectory_change_id=item.trajectory_change_id,
                )
            )
        self._session.commit()
        return follow_up

    def find_open_for_student(
        self, student_id: uuid.UUID, responsible_user_id: uuid.UUID
    ) -> FollowUp | None:
        stmt = (
            select(FollowUpModel)
            .where(
                FollowUpModel.student_id == student_id,
                FollowUpModel.responsible_user_id == responsible_user_id,
                FollowUpModel.status != FollowUpStatus.ENCERRADO,
            )
            .order_by(FollowUpModel.created_at.desc(), FollowUpModel.id.desc())
            .limit(1)
        )
        model = self._session.execute(stmt).scalars().first()
        if model is None:
            return None
        return FollowUp(
            id=model.id,
            student_id=model.student_id,
            status=model.status,
            reason=model.reason,
            responsible_user_id=model.responsible_user_id,
            next_review_date=model.next_review_date,
            created_at=model.created_at,
        )

    def add_evidence(self, evidence: FollowUpEvidence) -> FollowUpEvidence:
        self._session.add(
            FollowUpEvidenceModel(
                id=evidence.id,
                follow_up_id=evidence.follow_up_id,
                trajectory_change_id=evidence.trajectory_change_id,
            )
        )
        self._session.commit()
        return evidence

    def get_by_id(self, follow_up_id: uuid.UUID) -> FollowUp | None:
        model = self._session.get(FollowUpModel, follow_up_id)
        if model is None:
            return None
        return FollowUp(
            id=model.id,
            student_id=model.student_id,
            status=model.status,
            reason=model.reason,
            responsible_user_id=model.responsible_user_id,
            next_review_date=model.next_review_date,
            created_at=model.created_at,
        )

    def list_active(self) -> list[FollowUp]:
        # spec-4-5: every `FollowUp` whose status is not `ENCERRADO` (never
        # capped/paginated — open-case volume is operator-driven, unlike the
        # high-volume synthetic `TrajectoryChange` rows `list_recent` caps).
        stmt = (
            select(FollowUpModel)
            .where(FollowUpModel.status != FollowUpStatus.ENCERRADO)
            .order_by(FollowUpModel.created_at.desc(), FollowUpModel.id.desc())
        )
        models = self._session.execute(stmt).scalars().all()
        return [
            FollowUp(
                id=model.id,
                student_id=model.student_id,
                status=model.status,
                reason=model.reason,
                responsible_user_id=model.responsible_user_id,
                next_review_date=model.next_review_date,
                created_at=model.created_at,
            )
            for model in models
        ]

    def list_evidence_by_follow_up(self, follow_up_id: uuid.UUID) -> list[FollowUpEvidence]:
        # Joined to `trajectory_changes` purely to order by its `detected_at`
        # (spec Code Map) — `GetFollowUpService` still loads each
        # `TrajectoryChange` separately via `TrajectoryChangeRepositoryPort`.
        stmt = (
            select(FollowUpEvidenceModel)
            .join(
                TrajectoryChangeModel,
                TrajectoryChangeModel.id == FollowUpEvidenceModel.trajectory_change_id,
            )
            .where(FollowUpEvidenceModel.follow_up_id == follow_up_id)
            .order_by(TrajectoryChangeModel.detected_at.asc(), FollowUpEvidenceModel.id.asc())
        )
        models = self._session.execute(stmt).scalars().all()
        return [
            FollowUpEvidence(
                id=model.id,
                follow_up_id=model.follow_up_id,
                trajectory_change_id=model.trajectory_change_id,
            )
            for model in models
        ]

    def list_actions_by_follow_up(self, follow_up_id: uuid.UUID) -> list[FollowUpAction]:
        stmt = (
            select(FollowUpActionModel)
            .where(FollowUpActionModel.follow_up_id == follow_up_id)
            .order_by(FollowUpActionModel.created_at.asc(), FollowUpActionModel.id.asc())
        )
        models = self._session.execute(stmt).scalars().all()
        return [
            FollowUpAction(
                id=model.id,
                follow_up_id=model.follow_up_id,
                description=model.description,
                author_user_id=model.author_user_id,
                created_at=model.created_at,
            )
            for model in models
        ]

    def add_action(self, action: FollowUpAction) -> FollowUpAction:
        self._session.add(
            FollowUpActionModel(
                id=action.id,
                follow_up_id=action.follow_up_id,
                description=action.description,
                author_user_id=action.author_user_id,
                created_at=action.created_at,
            )
        )
        self._session.commit()
        return action

    def update_status(
        self, follow_up_id: uuid.UUID, status: FollowUpStatus
    ) -> FollowUp | None:
        model = self._session.get(FollowUpModel, follow_up_id)
        if model is None:
            return None
        # The one and only `FollowUpModel.status =` assignment in the
        # codebase (spec Code Map, AD-6) — reached only via
        # `ChangeFollowUpStatusService`, never the router.
        model.status = status
        self._session.commit()
        return FollowUp(
            id=model.id,
            student_id=model.student_id,
            status=model.status,
            reason=model.reason,
            responsible_user_id=model.responsible_user_id,
            next_review_date=model.next_review_date,
            created_at=model.created_at,
        )
