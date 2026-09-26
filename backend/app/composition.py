"""Composition root — the only place allowed to import concrete
`infrastructure/` classes and wire them into `application/` services or
ports. `presentation/` (routers, dependencies) imports only the factory
functions below, never `infrastructure/` itself (AD-2: "presentation...
nunca acessa infrastructure diretamente").
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.attendance.list_classrooms import ListClassroomsService
from app.application.attendance.list_enrolled_students import ListEnrolledStudentsService
from app.application.attendance.register_attendance import RegisterAttendanceService
from app.application.auth.authenticate_user import AuthenticateUserService
from app.config import Settings, get_settings
from app.infrastructure.db.base import get_db
from app.infrastructure.repositories.sqlalchemy_attendance_repository import (
    SqlAlchemyAttendanceRepository,
)
from app.infrastructure.repositories.sqlalchemy_classroom_repository import (
    SqlAlchemyClassroomRepository,
)
from app.infrastructure.repositories.sqlalchemy_student_repository import SqlAlchemyStudentRepository
from app.infrastructure.repositories.sqlalchemy_user_repository import SqlAlchemyUserRepository
from app.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher
from app.infrastructure.security.jwt_issuer import JwtTokenIssuer


def get_token_issuer(settings: Settings = Depends(get_settings)) -> JwtTokenIssuer:
    return JwtTokenIssuer(settings)


def get_authenticate_user_service(
    db: Session = Depends(get_db),
    token_issuer: JwtTokenIssuer = Depends(get_token_issuer),
) -> AuthenticateUserService:
    return AuthenticateUserService(
        user_repository=SqlAlchemyUserRepository(db),
        password_hasher=BcryptPasswordHasher(),
        token_issuer=token_issuer,
    )


def get_list_classrooms_service(db: Session = Depends(get_db)) -> ListClassroomsService:
    return ListClassroomsService(classroom_repository=SqlAlchemyClassroomRepository(db))


def get_list_enrolled_students_service(
    db: Session = Depends(get_db),
) -> ListEnrolledStudentsService:
    return ListEnrolledStudentsService(
        classroom_repository=SqlAlchemyClassroomRepository(db),
        student_repository=SqlAlchemyStudentRepository(db),
    )


def get_register_attendance_service(db: Session = Depends(get_db)) -> RegisterAttendanceService:
    return RegisterAttendanceService(
        classroom_repository=SqlAlchemyClassroomRepository(db),
        student_repository=SqlAlchemyStudentRepository(db),
        attendance_repository=SqlAlchemyAttendanceRepository(db),
    )
