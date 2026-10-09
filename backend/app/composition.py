"""Composition root — the only place allowed to import concrete
`infrastructure/` classes and wire them into `application/` services or
ports. `presentation/` (routers, dependencies) imports only the factory
functions below, never `infrastructure/` itself (AD-2: "presentation...
nunca acessa infrastructure diretamente").
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.academic_periods.list_academic_periods import ListAcademicPeriodsService
from app.application.assignments.list_assignments import ListAssignmentsByClassroomService
from app.application.assignments.register_assignment import RegisterAssignmentService
from app.application.assignments.register_submission import RegisterSubmissionService
from app.application.attendance.list_classrooms import ListClassroomsService
from app.application.attendance.list_enrolled_students import ListEnrolledStudentsService
from app.application.attendance.register_attendance import RegisterAttendanceService
from app.application.auth.authenticate_user import AuthenticateUserService
from app.application.grades.register_grade import RegisterGradeService
from app.application.observations.register_observation import RegisterObservationService
from app.application.trajectory.get_student_trajectory import GetStudentTrajectoryService
from app.config import Settings, get_settings
from app.infrastructure.db.base import get_db
from app.infrastructure.repositories.sqlalchemy_academic_period_repository import (
    SqlAlchemyAcademicPeriodRepository,
)
from app.infrastructure.repositories.sqlalchemy_assignment_repository import (
    SqlAlchemyAssignmentRepository,
)
from app.infrastructure.repositories.sqlalchemy_assignment_submission_repository import (
    SqlAlchemyAssignmentSubmissionRepository,
)
from app.infrastructure.repositories.sqlalchemy_attendance_repository import (
    SqlAlchemyAttendanceRepository,
)
from app.infrastructure.repositories.sqlalchemy_classroom_repository import (
    SqlAlchemyClassroomRepository,
)
from app.infrastructure.repositories.sqlalchemy_grade_repository import SqlAlchemyGradeRepository
from app.infrastructure.repositories.sqlalchemy_pedagogical_observation_repository import (
    SqlAlchemyPedagogicalObservationRepository,
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


def get_list_academic_periods_service(db: Session = Depends(get_db)) -> ListAcademicPeriodsService:
    return ListAcademicPeriodsService(
        academic_period_repository=SqlAlchemyAcademicPeriodRepository(db)
    )


def get_register_grade_service(db: Session = Depends(get_db)) -> RegisterGradeService:
    return RegisterGradeService(
        classroom_repository=SqlAlchemyClassroomRepository(db),
        student_repository=SqlAlchemyStudentRepository(db),
        academic_period_repository=SqlAlchemyAcademicPeriodRepository(db),
        grade_repository=SqlAlchemyGradeRepository(db),
    )


def get_register_assignment_service(db: Session = Depends(get_db)) -> RegisterAssignmentService:
    return RegisterAssignmentService(
        classroom_repository=SqlAlchemyClassroomRepository(db),
        academic_period_repository=SqlAlchemyAcademicPeriodRepository(db),
        assignment_repository=SqlAlchemyAssignmentRepository(db),
    )


def get_list_assignments_by_classroom_service(
    db: Session = Depends(get_db),
) -> ListAssignmentsByClassroomService:
    return ListAssignmentsByClassroomService(
        classroom_repository=SqlAlchemyClassroomRepository(db),
        assignment_repository=SqlAlchemyAssignmentRepository(db),
    )


def get_register_submission_service(db: Session = Depends(get_db)) -> RegisterSubmissionService:
    return RegisterSubmissionService(
        assignment_repository=SqlAlchemyAssignmentRepository(db),
        student_repository=SqlAlchemyStudentRepository(db),
        assignment_submission_repository=SqlAlchemyAssignmentSubmissionRepository(db),
    )


def get_register_observation_service(db: Session = Depends(get_db)) -> RegisterObservationService:
    return RegisterObservationService(
        classroom_repository=SqlAlchemyClassroomRepository(db),
        student_repository=SqlAlchemyStudentRepository(db),
        observation_repository=SqlAlchemyPedagogicalObservationRepository(db),
    )


def get_get_student_trajectory_service(
    db: Session = Depends(get_db),
) -> GetStudentTrajectoryService:
    return GetStudentTrajectoryService(
        student_repository=SqlAlchemyStudentRepository(db),
        attendance_repository=SqlAlchemyAttendanceRepository(db),
        grade_repository=SqlAlchemyGradeRepository(db),
        assignment_repository=SqlAlchemyAssignmentRepository(db),
        assignment_submission_repository=SqlAlchemyAssignmentSubmissionRepository(db),
        academic_period_repository=SqlAlchemyAcademicPeriodRepository(db),
    )
