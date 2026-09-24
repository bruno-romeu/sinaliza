"""SQLAlchemy models — the only place ORM concerns exist (AD-2)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer
from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.attendance import AttendanceStatus
from app.domain.student import DatasetSplit
from app.domain.user import UserRole
from app.infrastructure.db.base import Base

user_role_enum = SAEnum(UserRole, name="user_role", native_enum=True, validate_strings=True)
dataset_split_enum = SAEnum(DatasetSplit, name="dataset_split", native_enum=True, validate_strings=True)
attendance_status_enum = SAEnum(
    AttendanceStatus, name="attendance_status", native_enum=True, validate_strings=True
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
    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_split: Mapped[DatasetSplit] = mapped_column(dataset_split_enum, nullable=False)


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
