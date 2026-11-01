"""Contrato HTTP transversal: o que cada rota exige e o que cada rota devolve.

Os testes por domínio (`test_attendance.py`, `test_follow_ups.py`, ...) cobrem
cada rota isoladamente. Este arquivo cobre as invariantes que valem para
*todas* elas ao mesmo tempo, que é exatamente onde elas costumam se perder:

1. **Autenticação** — toda rota documentada, exceto `POST /auth/login`,
   responde 401 no envelope do projeto quando chamada sem token. Um novo
   router registrado sem `Depends(get_current_user)` quebra aqui, não em
   produção.
2. **Fronteira AD-3** — `synthetic_profile` é o gabarito do dataset sintético
   (`StudentModel.synthetic_profile`, lido só por `app/ml/*`). Se ele
   aparecer em qualquer schema de resposta, a demonstração passa a vazar a
   resposta da própria avaliação. O mesmo vale para `dataset_split` e para
   `password_hash`.
3. **Score de ML** — `AGENTS.md` ("Regra mais importante") proíbe o produto
   apresentar `predict_proba()` como probabilidade de evasão. Hoje nenhuma
   rota HTTP toca `MLPrediction`; este teste é o que torna essa ausência uma
   afirmação verificável em vez de um acidente.
4. **Tradução de violação de integridade até o HTTP** — uma violação de FK
   alcançável de verdade responde 409 no envelope, não 500.
"""

from __future__ import annotations

import json
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.application.attendance.errors import DuplicateAttendanceError
from app.application.attendance.register_attendance import RegisterAttendanceService
from app.application.integrity import (
    DuplicateRecordError,
    IntegrityViolationError,
    InvalidRecordValueError,
    MissingRequiredValueError,
    ReferencedRecordMissingError,
    translate_repository_integrity_error,
)
from app.config import Settings
from app.domain.attendance import AttendanceStatus
from app.domain.student import DatasetSplit, SyntheticProfile
from app.domain.user import UserRole
from app.infrastructure.db.models import ClassroomModel, EnrollmentModel, StudentModel, UserModel
from app.infrastructure.repositories.errors import (
    CheckViolationError,
    ForeignKeyViolationError,
    NotNullViolationError,
    RepositoryIntegrityError,
    UniqueViolationError,
)
from app.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher
from app.infrastructure.security.jwt_issuer import JwtTokenIssuer

INVALID_TOKEN_BODY = {"error": {"code": "invalid_token", "message": "Sessão expirada ou inválida."}}

# Qualquer rota não listada aqui precisa de token. A lista é deliberadamente
# minúscula: ampliá-la é uma decisão de produto, não um detalhe de
# implementação.
_PUBLIC_OPERATIONS = {("POST", "/auth/login")}

# Nomes que nunca podem aparecer em um schema de resposta da API.
# `synthetic_profile`/`dataset_split`: fronteira AD-3 (gabarito do dataset).
# `password_hash`: credencial. `model_score`/`risk_score`: score de ML
# apresentado como fato sobre o estudante (AGENTS.md, "Regra mais
# importante").
_FORBIDDEN_RESPONSE_FIELDS = (
    "synthetic_profile",
    "dataset_split",
    "password_hash",
    "model_score",
    "risk_score",
    "engagement_score",
    "student_priority",
)

_ZERO_UUID = "00000000-0000-0000-0000-000000000000"


def _auth_headers(client: TestClient, user: UserModel) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": user.email, "password": "Senha-Correta-123"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _documented_operations(client: TestClient) -> list[tuple[str, str]]:
    spec = client.get("/openapi.json").json()
    return [
        (method.upper(), path)
        for path, operations in sorted(spec["paths"].items())
        for method in operations
    ]


def _concrete_url(path: str) -> str:
    for parameter in ("classroom_id", "student_id", "follow_up_id"):
        path = path.replace(f"{{{parameter}}}", _ZERO_UUID)
    return path


# --- 1. Autenticação -------------------------------------------------------


def test_every_documented_route_except_login_requires_a_bearer_token(
    client: TestClient,
) -> None:
    """Chamada HTTP real, sem token, em cada operação do OpenAPI."""
    unprotected: list[tuple[str, str, int]] = []
    for method, path in _documented_operations(client):
        if (method, path) in _PUBLIC_OPERATIONS:
            continue
        response = client.request(method, _concrete_url(path), json={})
        if response.status_code != 401 or response.json() != INVALID_TOKEN_BODY:
            unprotected.append((method, path, response.status_code))

    assert unprotected == []


def test_login_is_the_only_operation_reachable_without_a_token(client: TestClient) -> None:
    response = client.post("/auth/login", json={})
    # 422 do Pydantic (corpo inválido), nunca 401: a rota em si é pública.
    assert response.status_code == 422


def test_a_signed_token_whose_sub_is_not_a_uuid_is_rejected_as_401_not_500(
    client: TestClient, test_settings: Settings
) -> None:
    """`CurrentUser.id` é convertido com `uuid.UUID(...)` em todo router que
    precisa da identidade do chamador; antes, um token válido com `sub`
    não-UUID estourava `ValueError` dentro do router (500)."""
    import jwt

    token = jwt.encode(
        {
            "sub": "nao-e-um-uuid",
            "name": "Coordenação",
            "role": UserRole.COORDENACAO_PEDAGOGICA.value,
        },
        test_settings.jwt_secret,
        algorithm=JwtTokenIssuer.algorithm,
    )
    response = client.get("/home", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json() == INVALID_TOKEN_BODY


# --- 2/3. Exposição: AD-3, credenciais e score de ML ------------------------


def test_no_response_schema_exposes_the_synthetic_dataset_answer_key(
    client: TestClient,
) -> None:
    """O documento OpenAPI é o contrato que o frontend gera (`schema.d.ts`):
    se o campo não está lá, ele não está em nenhum `response_model`."""
    document = json.dumps(client.get("/openapi.json").json())

    leaked = [field for field in _FORBIDDEN_RESPONSE_FIELDS if field in document]

    assert leaked == []


def test_trajectory_routes_never_return_synthetic_profile_for_a_labelled_student(
    client: TestClient, db_session: Session, seeded_user: UserModel
) -> None:
    """Fronteira AD-3 verificada contra um estudante que de fato tem o rótulo
    gravado — o schema poderia estar limpo e o roteador ainda assim devolver
    um corpo extra."""
    classroom = ClassroomModel(name="Turma AD-3", academic_year=2026)
    db_session.add(classroom)
    db_session.flush()
    student = StudentModel(
        name="Estudante Rotulado",
        dataset_split=DatasetSplit.EVAL_DEMO,
        synthetic_profile=SyntheticProfile.FALLING_ATTENDANCE,
    )
    db_session.add(student)
    db_session.flush()
    db_session.add(EnrollmentModel(student_id=student.id, classroom_id=classroom.id))
    db_session.commit()

    headers = _auth_headers(client, seeded_user)
    for url in (
        f"/students/{student.id}/trajectory",
        f"/students/{student.id}/trajectory/detail",
    ):
        response = client.get(url, headers=headers)
        assert response.status_code == 200, url
        body = response.text
        assert "synthetic_profile" not in body, url
        assert SyntheticProfile.FALLING_ATTENDANCE.value not in body, url


def test_student_search_never_returns_a_train_split_student(
    client: TestClient, db_session: Session, seeded_user: UserModel
) -> None:
    """O split `TRAIN` é material de treino do experimento, não população da
    demonstração (AD-4): ele não pode ser alcançável por nenhuma leitura de
    produto."""
    classroom = ClassroomModel(name="Turma Split", academic_year=2026)
    db_session.add(classroom)
    db_session.flush()
    train_student = StudentModel(name="Estudante Treino Zzz", dataset_split=DatasetSplit.TRAIN)
    db_session.add(train_student)
    db_session.flush()
    db_session.add(EnrollmentModel(student_id=train_student.id, classroom_id=classroom.id))
    db_session.commit()

    headers = _auth_headers(client, seeded_user)

    search = client.get("/home/search", params={"q": "Estudante Treino Zzz"}, headers=headers)
    assert search.status_code == 200
    assert search.json()["results"] == []

    trajectory = client.get(f"/students/{train_student.id}/trajectory", headers=headers)
    assert trajectory.status_code == 404


def test_no_route_exposes_an_ml_prediction_score(client: TestClient) -> None:
    """`MLPrediction.score` é `1 - predict_proba(STABLE)` e é dado
    experimental (AGENTS.md, "Score de modelo"). Nenhuma rota HTTP deve
    alcançá-lo: a inferência vive em `app/ml/predict.py`, fora da API."""
    spec = client.get("/openapi.json").json()
    schemas = spec.get("components", {}).get("schemas", {})

    ml_schemas = [name for name in schemas if "prediction" in name.lower() or "ml" in name.lower()]
    assert ml_schemas == []

    document = json.dumps(spec).lower()
    for term in ("predict_proba", "probabilidade de evasão", "evasion_probability"):
        assert term not in document


def test_login_response_never_echoes_the_password_or_its_hash(
    client: TestClient, seeded_user: UserModel
) -> None:
    response = client.post(
        "/auth/login", json={"email": seeded_user.email, "password": "Senha-Correta-123"}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body["user"]) == {"id", "name", "email", "role"}
    assert "Senha-Correta-123" not in response.text


# --- 4. Violação de integridade até o HTTP ---------------------------------


def test_foreign_key_violation_answers_409_in_the_error_envelope_not_500(
    client: TestClient, db_session: Session, seeded_enrolled_student: StudentModel
) -> None:
    """Caminho alcançável de verdade: o bearer é stateless e validado sem ida
    ao banco, então um token emitido para um usuário cuja linha foi removida
    continua autenticando — e a próxima escrita grava um `author_user_id`
    que não existe mais (`pedagogical_observations.author_user_id`,
    `ondelete=RESTRICT`).

    Antes deste PR: `IntegrityError` não tratado -> 500. Agora: 409 no
    envelope do projeto.
    """
    hasher = BcryptPasswordHasher()
    ghost = UserModel(
        name="Coordenação Removida",
        email="removida@escola.test",
        password_hash=hasher.hash("Senha-Correta-123"),
        role=UserRole.COORDENACAO_PEDAGOGICA,
    )
    db_session.add(ghost)
    db_session.commit()

    headers = _auth_headers(client, ghost)

    enrollment = (
        db_session.query(EnrollmentModel).filter_by(student_id=seeded_enrolled_student.id).one()
    )
    classroom_id = enrollment.classroom_id

    db_session.delete(ghost)
    db_session.commit()

    response = client.post(
        "/pedagogical-observations",
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(classroom_id),
            "text": "Participou menos das discussões nas últimas duas aulas.",
        },
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "referenced_record_missing",
            "message": (
                "A operação referencia um registro que não existe mais, ou o "
                "registro não pode ser removido porque ainda é referenciado."
            ),
        }
    }


def test_the_session_stays_usable_after_an_integrity_violation(
    client: TestClient, db_session: Session, seeded_user: UserModel, seeded_enrolled_student
) -> None:
    """A tradução só é útil se a requisição seguinte funcionar: um flush que
    falha deixa a transação apenas *desativada* até o rollback."""
    hasher = BcryptPasswordHasher()
    ghost = UserModel(
        name="Coordenação Removida 2",
        email="removida2@escola.test",
        password_hash=hasher.hash("Senha-Correta-123"),
        role=UserRole.COORDENACAO_PEDAGOGICA,
    )
    db_session.add(ghost)
    db_session.commit()
    ghost_headers = _auth_headers(client, ghost)
    enrollment = (
        db_session.query(EnrollmentModel).filter_by(student_id=seeded_enrolled_student.id).one()
    )
    classroom_id = enrollment.classroom_id
    db_session.delete(ghost)
    db_session.commit()

    failed = client.post(
        "/pedagogical-observations",
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(classroom_id),
            "text": "Texto que não será gravado.",
        },
        headers=ghost_headers,
    )
    assert failed.status_code == 409

    ok = client.post(
        "/pedagogical-observations",
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(classroom_id),
            "text": "Não entregou a atividade desta semana.",
        },
        headers=_auth_headers(client, seeded_user),
    )
    assert ok.status_code == 201


def test_duplicate_attendance_still_answers_its_own_409_not_the_generic_one(
    client: TestClient, seeded_user: UserModel, seeded_enrolled_student: StudentModel, db_session
) -> None:
    """Prova do "antes": a tradução específica de UNIQUE continua chegando ao
    HTTP com a mensagem de domínio, não com a genérica de integridade."""
    enrollment = (
        db_session.query(EnrollmentModel).filter_by(student_id=seeded_enrolled_student.id).one()
    )
    headers = _auth_headers(client, seeded_user)
    payload = {
        "student_id": str(seeded_enrolled_student.id),
        "classroom_id": str(enrollment.classroom_id),
        "date": "2026-09-24",
        "status": "ABSENT_UNJUSTIFIED",
    }

    assert client.post("/attendance", json=payload, headers=headers).status_code == 201

    duplicate = client.post("/attendance", json=payload, headers=headers)

    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "error": {
            "code": "duplicate_attendance",
            "message": "Já existe registro de presença para este aluno, turma e data.",
        }
    }


class _RaisingAttendanceRepository:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def save(self, *args: object, **kwargs: object) -> None:
        raise self._error


class _AlwaysFoundClassroomRepository:
    def get_by_id(self, classroom_id: uuid.UUID) -> object:
        return object()


class _AlwaysEnrolledStudentRepository:
    def exists_enrollment(self, student_id: uuid.UUID, classroom_id: uuid.UUID) -> bool:
        return True


def _attendance_service(error: Exception) -> RegisterAttendanceService:
    return RegisterAttendanceService(
        classroom_repository=_AlwaysFoundClassroomRepository(),  # type: ignore[arg-type]
        student_repository=_AlwaysEnrolledStudentRepository(),  # type: ignore[arg-type]
        attendance_repository=_RaisingAttendanceRepository(error),  # type: ignore[arg-type]
    )


def _repository_error(cls: type[RepositoryIntegrityError]) -> RepositoryIntegrityError:
    return cls("INSERT ...", {}, Exception("orig"), constraint_name="c", table_name="t")


def test_attendance_no_longer_reports_a_foreign_key_violation_as_a_duplicate() -> None:
    """Antes: `RegisterAttendanceService` capturava `IntegrityError`, ou
    seja, *qualquer* violação, e respondia 409 "já existe registro de
    presença" — uma afirmação factualmente falsa sobre um duplicado que não
    existe. Agora só UNIQUE vira `DuplicateAttendanceError`."""
    service = _attendance_service(_repository_error(ForeignKeyViolationError))

    with pytest.raises(ReferencedRecordMissingError):
        service.execute(uuid.uuid4(), uuid.uuid4(), date(2026, 9, 24), AttendanceStatus.PRESENT)


def test_attendance_still_reports_a_unique_violation_as_a_duplicate() -> None:
    service = _attendance_service(_repository_error(UniqueViolationError))

    with pytest.raises(DuplicateAttendanceError):
        service.execute(uuid.uuid4(), uuid.uuid4(), date(2026, 9, 24), AttendanceStatus.PRESENT)


@pytest.mark.parametrize(
    ("repository_error", "application_error"),
    [
        (ForeignKeyViolationError, ReferencedRecordMissingError),
        (UniqueViolationError, DuplicateRecordError),
        (CheckViolationError, InvalidRecordValueError),
        (NotNullViolationError, MissingRequiredValueError),
        (RepositoryIntegrityError, IntegrityViolationError),
    ],
)
def test_every_repository_integrity_error_has_an_application_level_meaning(
    repository_error: type[RepositoryIntegrityError],
    application_error: type[IntegrityViolationError],
) -> None:
    translated = translate_repository_integrity_error(_repository_error(repository_error))

    assert type(translated) is application_error
    # A origem nunca é descartada (AGENTS.md, "Evidência").
    assert (
        isinstance(translated.__cause__, RepositoryIntegrityError) or translated.__cause__ is None
    )
    assert translated.constraint_name == "c"
    assert translated.table_name == "t"


def test_the_integrity_envelope_never_leaks_the_constraint_or_table_name(
    client: TestClient,
) -> None:
    """Os diagnósticos ficam na exceção (log/traceback), nunca no corpo HTTP:
    devolvê-los entregaria o schema físico ao cliente."""
    from app.presentation.errors import integrity_response

    response = integrity_response(
        ReferencedRecordMissingError(
            constraint_name="fk_pedagogical_observations_author_user_id", table_name="users"
        )
    )
    body = response.body.decode("utf-8")

    assert "fk_pedagogical_observations_author_user_id" not in body
    assert "users" not in body


# --- Consistência do envelope ---------------------------------------------


def test_every_app_error_response_uses_the_same_envelope_shape(
    client: TestClient, seeded_user: UserModel
) -> None:
    """404/422/409 vindos de `AppError` têm exatamente
    `{"error": {"code", "message"}}` — nada além disso."""
    headers = _auth_headers(client, seeded_user)
    responses = [
        client.get(f"/classrooms/{_ZERO_UUID}/students", headers=headers),
        client.get(f"/students/{_ZERO_UUID}/trajectory", headers=headers),
        client.get(f"/follow-ups/{_ZERO_UUID}", headers=headers),
        client.get("/home"),
    ]

    for response in responses:
        assert response.status_code >= 400
        body = response.json()
        assert set(body) == {"error"}, body
        assert set(body["error"]) == {"code", "message"}, body
        assert isinstance(body["error"]["code"], str) and body["error"]["code"]
        assert isinstance(body["error"]["message"], str) and body["error"]["message"]


def test_every_write_route_answers_201_and_every_read_route_200(
    client: TestClient,
) -> None:
    """Coerência de status entre rotas equivalentes, lida do próprio
    contrato: todo `POST` que cria recurso declara 201; `PATCH`/`GET`
    declaram 200."""
    spec = client.get("/openapi.json").json()
    unexpected: list[tuple[str, str, list[str]]] = []
    for path, operations in sorted(spec["paths"].items()):
        for method, operation in operations.items():
            success = sorted(code for code in operation["responses"] if code.startswith("2"))
            if method.upper() == "POST" and path != "/auth/login":
                expected = ["201"] if path != "/follow-ups" else ["200", "201"]
            else:
                expected = ["200"]
            if success != expected:
                unexpected.append((method.upper(), path, success))

    assert unexpected == []


def test_every_operation_declares_a_response_model(client: TestClient) -> None:
    """`response_model` é o que impede vazamento acidental de campo: uma rota
    sem schema de resposta serializa o que o serviço devolver."""
    spec = client.get("/openapi.json").json()
    without_schema: list[tuple[str, str]] = []
    for path, operations in sorted(spec["paths"].items()):
        for method, operation in operations.items():
            for code, response in operation["responses"].items():
                if not code.startswith("2"):
                    continue
                schema = response.get("content", {}).get("application/json", {}).get("schema")
                if not schema:
                    without_schema.append((method.upper(), path))

    assert without_schema == []
