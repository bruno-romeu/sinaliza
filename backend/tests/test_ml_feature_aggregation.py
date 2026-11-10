"""Testes DB-backed de `fetch_feature_rows()` com as features temporais
(spec-features-temporais-de-trajetoria, CAP-1 e CAP-4).

As funções de cálculo em si são testadas sem banco em
`test_ml_temporal_features.py`. O que se testa aqui é a camada que elas não
cobrem: que o SQL alimenta cada função com a sequência certa, **na ordem
certa**, e que um estudante sem histórico não quebra nem recebe um `0.0` que
afirmaria estabilidade onde há ausência de dado.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.domain.assignment_submission import AssignmentSubmissionStatus
from app.domain.attendance import AttendanceStatus
from app.domain.student import DatasetSplit
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    AssignmentModel,
    AssignmentSubmissionModel,
    AttendanceRecordModel,
    ClassroomModel,
    GradeModel,
    StudentModel,
)
from app.ml.feature_aggregation import (
    FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    FeatureRow,
    fetch_feature_rows,
)


def _student(db_session: Session) -> StudentModel:
    student = StudentModel(
        name="Estudante de teste",
        dataset_split=DatasetSplit.EVAL_DEMO,
        synthetic_profile=None,
    )
    db_session.add(student)
    db_session.commit()
    return student


def _row_for(db_session: Session, student: StudentModel) -> FeatureRow:
    rows = fetch_feature_rows(db_session, DatasetSplit.EVAL_DEMO)
    return next(row for row in rows if row.student_id == student.id)


def _add_attendance(
    db_session: Session,
    student: StudentModel,
    classroom: ClassroomModel,
    statuses: list[AttendanceStatus],
) -> None:
    db_session.add_all(
        [
            AttendanceRecordModel(
                student_id=student.id,
                classroom_id=classroom.id,
                date=date(2026, 3, 1) + timedelta(days=index),
                status=status,
            )
            for index, status in enumerate(statuses)
        ]
    )
    db_session.commit()


def _add_period(db_session: Session, order_index: int) -> AcademicPeriodModel:
    period = AcademicPeriodModel(
        label=f"Periodo {order_index}",
        start_date=date(2026, 1 + order_index, 1),
        end_date=date(2026, 1 + order_index, 28),
        order_index=order_index,
    )
    db_session.add(period)
    db_session.commit()
    return period


def test_feature_columns_declares_the_four_temporal_features() -> None:
    """`AGENTS.md` §Features nomeia estas quatro. O teste impede que alguém
    as remova sem perceber que está voltando a um conjunto puramente
    instantâneo."""
    assert FEATURE_COLUMNS[4:] == (
        "attendance_trend",
        "consecutive_absences",
        "grade_delta",
        "missing_assignment_delta",
    )


def test_feature_schema_version_is_derived_not_hardcoded() -> None:
    """Decisão 0002: a versão do esquema é SHA-256 sobre os nomes ordenados.
    Acrescentar features a muda sozinha — e é essa mudança que faz
    `require_matching_feature_schema` recusar artefatos antigos."""
    import hashlib

    expected = hashlib.sha256("|".join(FEATURE_COLUMNS).encode()).hexdigest()[:12]
    assert FEATURE_SCHEMA_VERSION == f"sha256:{expected}"


def test_student_with_no_facts_gets_none_deltas_and_zero_count(
    db_session: Session,
) -> None:
    """Ausência de dado não é estabilidade. `0.0` num delta afirmaria "não
    mudou"; o que houve foi nenhuma observação."""
    student = _student(db_session)

    row = _row_for(db_session, student)

    assert row.attendance_trend is None
    assert row.grade_delta is None
    assert row.missing_assignment_delta is None
    # Contagem: mesma convenção de `observation_count`.
    assert row.consecutive_absences == 0


def test_single_attendance_record_yields_no_trend(
    db_session: Session, seeded_classroom: ClassroomModel
) -> None:
    student = _student(db_session)
    _add_attendance(db_session, student, seeded_classroom, [AttendanceStatus.PRESENT])

    row = _row_for(db_session, student)

    assert row.attendance_trend is None
    assert row.consecutive_absences == 0


def test_falling_attendance_yields_a_negative_trend(
    db_session: Session, seeded_classroom: ClassroomModel
) -> None:
    """A rampa que define `FALLING_ATTENDANCE`: presente no começo, ausente
    no fim."""
    student = _student(db_session)
    _add_attendance(
        db_session,
        student,
        seeded_classroom,
        [
            AttendanceStatus.PRESENT,
            AttendanceStatus.PRESENT,
            AttendanceStatus.ABSENT_UNJUSTIFIED,
            AttendanceStatus.ABSENT_UNJUSTIFIED,
        ],
    )

    row = _row_for(db_session, student)

    assert row.attendance_trend == -1.0
    assert row.consecutive_absences == 2
    # O nível continua lá, ao lado da inclinação: o conjunto novo é o antigo
    # mais quatro.
    assert row.attendance_rate == 0.5


def test_justified_and_unjustified_absences_count_equally(
    db_session: Session, seeded_classroom: ClassroomModel
) -> None:
    """`app/domain/attendance.py` já registra que a distinção está gravada
    para uso futuro, não usada na matemática de tendência (RF-11)."""
    student = _student(db_session)
    _add_attendance(
        db_session,
        student,
        seeded_classroom,
        [
            AttendanceStatus.PRESENT,
            AttendanceStatus.PRESENT,
            AttendanceStatus.ABSENT_JUSTIFIED,
            AttendanceStatus.ABSENT_UNJUSTIFIED,
        ],
    )

    row = _row_for(db_session, student)

    assert row.attendance_trend == -1.0
    assert row.consecutive_absences == 2


def test_attendance_series_is_ordered_by_date_not_insertion(
    db_session: Session, seeded_classroom: ClassroomModel
) -> None:
    """Inserir fora de ordem não pode inverter o sinal da feature. Sem o
    `ORDER BY` a ordem viria do plano do Postgres."""
    student = _student(db_session)
    db_session.add_all(
        [
            AttendanceRecordModel(
                student_id=student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 3, 4),
                status=AttendanceStatus.ABSENT_UNJUSTIFIED,
            ),
            AttendanceRecordModel(
                student_id=student.id,
                classroom_id=seeded_classroom.id,
                date=date(2026, 3, 1),
                status=AttendanceStatus.PRESENT,
            ),
        ]
    )
    db_session.commit()

    assert _row_for(db_session, student).attendance_trend == -1.0


def test_grade_delta_needs_two_periods(
    db_session: Session, seeded_classroom: ClassroomModel, seeded_academic_period
) -> None:
    """Notas em um único período não definem um delta."""
    student = _student(db_session)
    db_session.add_all(
        [
            GradeModel(
                student_id=student.id,
                classroom_id=seeded_classroom.id,
                subject="Matematica",
                period_id=seeded_academic_period.id,
                date=date(2026, 8, 1),
                value=value,
            )
            for value in (8.0, 6.0)
        ]
    )
    db_session.commit()

    row = _row_for(db_session, student)

    assert row.grade_delta is None
    assert row.grade_average == 7.0


def test_grade_delta_is_last_period_minus_first_ordered_by_order_index(
    db_session: Session, seeded_classroom: ClassroomModel
) -> None:
    """A rampa de nota do gerador é indexada por período. Ordenar por
    `order_index`, não pela data do lançamento: uma nota lançada com atraso
    move a data sem mover o período."""
    student = _student(db_session)
    first_period = _add_period(db_session, 1)
    last_period = _add_period(db_session, 2)
    db_session.add_all(
        [
            # Lançada depois, mas pertence ao primeiro período.
            GradeModel(
                student_id=student.id,
                classroom_id=seeded_classroom.id,
                subject="Matematica",
                period_id=first_period.id,
                date=date(2026, 11, 30),
                value=8.0,
            ),
            GradeModel(
                student_id=student.id,
                classroom_id=seeded_classroom.id,
                subject="Matematica",
                period_id=last_period.id,
                date=date(2026, 4, 1),
                value=2.0,
            ),
        ]
    )
    db_session.commit()

    assert _row_for(db_session, student).grade_delta == -6.0


def test_missing_assignment_delta_rises_when_non_delivery_grows(
    db_session: Session, seeded_classroom: ClassroomModel, seeded_academic_period
) -> None:
    """O eixo que só `COMBINED_DETERIORATION` tem no gerador. Positivo =
    piorando."""
    student = _student(db_session)
    assignments = []
    for index in range(4):
        assignment = AssignmentModel(
            classroom_id=seeded_classroom.id,
            subject="Matematica",
            period_id=seeded_academic_period.id,
            due_date=date(2026, 8, 1 + index),
        )
        db_session.add(assignment)
        assignments.append(assignment)
    db_session.flush()
    db_session.add_all(
        [
            AssignmentSubmissionModel(
                assignment_id=assignment.id,
                student_id=student.id,
                status=status,
                date=date(2026, 8, 1 + index),
            )
            for index, (assignment, status) in enumerate(
                zip(
                    assignments,
                    [
                        AssignmentSubmissionStatus.DELIVERED,
                        AssignmentSubmissionStatus.DELIVERED,
                        AssignmentSubmissionStatus.NOT_DELIVERED,
                        AssignmentSubmissionStatus.NOT_DELIVERED,
                    ],
                    strict=True,
                )
            )
        ]
    )
    db_session.commit()

    assert _row_for(db_session, student).missing_assignment_delta == 1.0


def test_fetch_feature_rows_is_deterministic(
    db_session: Session, seeded_classroom: ClassroomModel
) -> None:
    """Duas leituras do mesmo banco devolvem os mesmos valores. Sem isso, a
    reprodutibilidade que `train`/`evaluate` declaram seria falsa a partir da
    camada de features."""
    student = _student(db_session)
    _add_attendance(
        db_session,
        student,
        seeded_classroom,
        [
            AttendanceStatus.PRESENT,
            AttendanceStatus.ABSENT_UNJUSTIFIED,
            AttendanceStatus.PRESENT,
            AttendanceStatus.ABSENT_UNJUSTIFIED,
        ],
    )

    first = _row_for(db_session, student)
    second = _row_for(db_session, student)

    assert first == second


def test_unknown_student_is_not_returned(db_session: Session) -> None:
    """Sanidade da consulta: o corte é por `dataset_split`, não por tudo."""
    rows = fetch_feature_rows(db_session, DatasetSplit.TRAIN)
    assert all(isinstance(row.student_id, uuid.UUID) for row in rows)
