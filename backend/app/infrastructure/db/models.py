"""SQLAlchemy models — the only place ORM concerns exist (AD-2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, Text
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.assignment_submission import AssignmentSubmissionStatus
from app.domain.attendance import AttendanceStatus
from app.domain.follow_up import FollowUpStatus
from app.domain.student import DatasetSplit, SyntheticProfile
from app.domain.trajectory_change import SourceType, TrajectoryChangeType
from app.domain.user import UserRole
from app.infrastructure.db.base import Base

user_role_enum = SAEnum(UserRole, name="user_role", native_enum=True, validate_strings=True)
dataset_split_enum = SAEnum(DatasetSplit, name="dataset_split", native_enum=True, validate_strings=True)
attendance_status_enum = SAEnum(
    AttendanceStatus, name="attendance_status", native_enum=True, validate_strings=True
)
assignment_submission_status_enum = SAEnum(
    AssignmentSubmissionStatus,
    name="assignment_submission_status",
    native_enum=True,
    validate_strings=True,
)
synthetic_profile_enum = SAEnum(
    SyntheticProfile, name="synthetic_profile", native_enum=True, validate_strings=True
)
trajectory_change_type_enum = SAEnum(
    TrajectoryChangeType, name="trajectory_change_type", native_enum=True, validate_strings=True
)
trajectory_change_source_type_enum = SAEnum(
    SourceType, name="trajectory_change_source_type", native_enum=True, validate_strings=True
)
follow_up_status_enum = SAEnum(
    FollowUpStatus, name="follow_up_status", native_enum=True, validate_strings=True
)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        user_role_enum, nullable=False, default=UserRole.COORDENACAO_PEDAGOGICA
    )


class ClassroomModel(Base):
    __tablename__ = "classrooms"
    __table_args__ = (UniqueConstraint("name", name="uq_classroom_name"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False)


class StudentModel(Base):
    """`synthetic_profile` is nullable by design: a student created by
    `seed_dev_fixtures.py` has no profile, a student created by the synthetic
    generator eventually does (`data-model.md` §Geração sintética). Story 2.1
    ships the column always NULL — Story 2.2 owns populating it. It is the
    only in-code carrier of the research label and is never mapped into any
    Pydantic response schema (D2, AD-3's boundary)."""

    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_split: Mapped[DatasetSplit] = mapped_column(dataset_split_enum, nullable=False)
    synthetic_profile: Mapped[SyntheticProfile | None] = mapped_column(
        synthetic_profile_enum, nullable=True
    )


class EnrollmentModel(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "classroom_id", name="uq_enrollment_student_classroom"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True
    )
    classroom_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("classrooms.id"), nullable=False, index=True
    )


class AttendanceRecordModel(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("student_id", "classroom_id", "date", name="uq_attendance_student_classroom_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True
    )
    classroom_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("classrooms.id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[AttendanceStatus] = mapped_column(attendance_status_enum, nullable=False)


class AcademicPeriodModel(Base):
    """Dev-fixture seeded only (`seed_dev_fixtures.py`) — no registration
    screen (spec Boundaries & Constraints)."""

    __tablename__ = "academic_periods"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)


class GradeModel(Base):
    """`value` is `Numeric(4,2)` on a fixed 0.0–10.0 scale, structurally
    bounded by `ck_grade_value_range` — a DB-level CHECK, not just an
    application-layer/Pydantic check (spec Boundaries & Constraints, mirrors
    AD-7's "structural, not just app-checked" philosophy). No UNIQUE
    constraint — a student may legitimately receive multiple assessments in
    the same período (spec Boundaries & Constraints)."""

    __tablename__ = "grades"
    __table_args__ = (
        CheckConstraint("value >= 0 AND value <= 10", name="ck_grade_value_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True
    )
    classroom_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("classrooms.id"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    period_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("academic_periods.id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)


class AssignmentModel(Base):
    """No CHECK/UNIQUE beyond FK integrity — mirrors `GradeModel`'s
    precedent, no AC requires dedup (spec Boundaries & Constraints)."""

    __tablename__ = "assignments"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    classroom_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("classrooms.id"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    period_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("academic_periods.id"), nullable=False, index=True
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)


class AssignmentSubmissionModel(Base):
    """No UNIQUE constraint — a corrected/updated status is simply a new row
    (spec Boundaries & Constraints, mirrors `Grade`'s already-accepted
    no-dedup precedent)."""

    __tablename__ = "assignment_submissions"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assignments.id"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True
    )
    status: Mapped[AssignmentSubmissionStatus] = mapped_column(
        assignment_submission_status_enum, nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)


class PedagogicalObservationModel(Base):
    """No `follow_up_id`/FK to `FollowUp`/`TrajectoryChange` (data-model.md:
    it belongs to the student, not to a follow-up). No UNIQUE constraint —
    multiple observations per student are expected and valid, each a new row
    (spec Boundaries & Constraints, UX-DR13: "toda ação registrada entra no
    histórico, nunca substitui uma anterior"), mirroring `Grade`/
    `AssignmentSubmission`'s already-accepted no-dedup precedent."""

    __tablename__ = "pedagogical_observations"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrajectoryChangeModel(Base):
    """`UniqueConstraint("student_id", "type", "period_id")` is the upsert key
    (AD-1, spec Boundaries & Constraints) — writes always go through `INSERT
    ... ON CONFLICT ... DO UPDATE` against this index
    (`sqlalchemy_trajectory_change_repository.py`), never a `SELECT`-then-
    write. No `ondelete` on either FK — same unaddressed, already-accepted
    codebase-wide pattern as every other fact table here (see
    `deferred-work.md`)."""

    __tablename__ = "trajectory_changes"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "type", "period_id", name="uq_trajectory_change_student_type_period"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True
    )
    type: Mapped[TrajectoryChangeType] = mapped_column(trajectory_change_type_enum, nullable=False)
    period_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("academic_periods.id"), nullable=False, index=True
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class TrajectoryChangeSourceModel(Base):
    """`source_id` is necessarily polymorphic (points at `AttendanceRecord`,
    `Grade`, `AssignmentSubmission`, or `PedagogicalObservation` depending on
    `source_type`) so it carries no FK of its own — only `trajectory_change_id`
    is a real FK (data-model.md). No UNIQUE constraint — a single
    `TrajectoryChange` legitimately cites several source rows."""

    __tablename__ = "trajectory_change_sources"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trajectory_change_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("trajectory_changes.id"), nullable=False, index=True
    )
    source_type: Mapped[SourceType] = mapped_column(
        trajectory_change_source_type_enum, nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)


class FollowUpModel(Base):
    """No `ondelete` on either FK — same unaddressed, already-accepted
    codebase-wide pattern as `TrajectoryChangeModel`/`TrajectoryChangeSourceModel`
    (see `deferred-work.md`). `reason`/`next_review_date` are nullable: no UI
    captures them in this story (spec Boundaries & Constraints)."""

    __tablename__ = "follow_ups"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True
    )
    status: Mapped[FollowUpStatus] = mapped_column(follow_up_status_enum, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsible_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FollowUpEvidenceModel(Base):
    """`trajectory_change_id` is a real `NOT NULL` FK (RNF-11, AD-7) — unlike
    `TrajectoryChangeSource.source_id`, this is never polymorphic: a
    `FollowUpEvidence` row always points at exactly one `TrajectoryChange`."""

    __tablename__ = "follow_up_evidence"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    follow_up_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("follow_ups.id"), nullable=False, index=True
    )
    trajectory_change_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("trajectory_changes.id"), nullable=False, index=True
    )


class FollowUpActionModel(Base):
    """`description`/`author_user_id`/`created_at` make each row a fresh,
    append-only INSERT (spec Boundaries & Constraints, RF-13/RF-14) — the
    table also carries DB-level `GRANT INSERT, SELECT` / revoked
    `UPDATE`/`DELETE` for the app's role, applied in the Alembic migration
    and mirrored in `tests/conftest.py` so append-only-ness doesn't rely only
    on application code (AD-6)."""

    __tablename__ = "follow_up_action"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    follow_up_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("follow_ups.id"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SyntheticGenerationRunModel(Base):
    """One row per execution of `python -m app.synthetic.generate` — the
    persisted provenance RNF-13 requires (logging it would not survive the
    run). No UNIQUE on `seed`: the same seed may legitimately be re-run, and
    each execution is its own audit record.

    `seed` is `BigInteger` so a seed wider than 32 bits is still recordable;
    `train_ratio` is `Numeric(4,3)` rather than a float so the persisted
    proportion is exact — provenance that drifts by a float epsilon is not
    provenance.
    """

    __tablename__ = "synthetic_generation_runs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    generator_version: Mapped[str] = mapped_column(String(50), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    student_count: Mapped[int] = mapped_column(Integer, nullable=False)
    train_ratio: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)


class MLModelVersionModel(Base):
    """One row per successful `python -m app.ml.train` run (spec-5-1, RF-17)
    — never written by the web process (AD-3). `version` is `UNIQUE` so a
    re-run can never collide with or overwrite a prior row/artifact file
    (spec Never). `artifact_path` points at the single serialized sklearn
    `Pipeline` file Story 5.2's inference loader will later `joblib.load`."""

    __tablename__ = "ml_model_version"
    __table_args__ = (UniqueConstraint("version", name="uq_ml_model_version_version"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
