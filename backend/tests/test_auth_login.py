"""Covers every row of the spec's I/O & Edge-Case Matrix for `POST
/auth/login` and the scaffolded `get_current_user` dependency."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.user import User, UserRole
from app.infrastructure.db.models import UserModel
from app.infrastructure.security.jwt_issuer import JwtTokenIssuer
from app.presentation.auth.dependencies import get_current_user
from app.presentation.errors import AppError

INVALID_CREDENTIALS_BODY = {
    "error": {"code": "invalid_credentials", "message": "Login ou senha inválidos."}
}


def test_login_success_issues_bearer_token_and_returns_user(
    client: TestClient, seeded_user: UserModel
) -> None:
    response = client.post(
        "/auth/login", json={"email": seeded_user.email, "password": "Senha-Correta-123"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]
    assert body["user"] == {
        "id": str(seeded_user.id),
        "name": seeded_user.name,
        "email": seeded_user.email,
        "role": "COORDENACAO_PEDAGOGICA",
    }


def test_login_wrong_password_returns_generic_401_and_no_token(
    client: TestClient, seeded_user: UserModel
) -> None:
    response = client.post(
        "/auth/login", json={"email": seeded_user.email, "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json() == INVALID_CREDENTIALS_BODY


def test_login_unknown_email_returns_identical_401(client: TestClient, seeded_user: UserModel) -> None:
    response = client.post(
        "/auth/login", json={"email": "does-not-exist@escola.test", "password": "whatever"}
    )

    assert response.status_code == 401
    assert response.json() == INVALID_CREDENTIALS_BODY


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "", "password": "Senha-Correta-123"},
        {"email": "coordenacao@escola.test", "password": ""},
        {"password": "Senha-Correta-123"},
        {"email": "coordenacao@escola.test"},
        {},
    ],
)
def test_login_malformed_body_returns_default_fastapi_validation_error(
    client: TestClient, payload: dict
) -> None:
    response = client.post("/auth/login", json=payload)

    assert response.status_code == 422
    body = response.json()
    # FastAPI's default validation envelope (`detail: [...]`) — not the auth
    # error envelope.
    assert "detail" in body
    assert "error" not in body


def test_password_is_hashed_never_plaintext(seeded_user: UserModel) -> None:
    assert seeded_user.password_hash != "Senha-Correta-123"
    assert seeded_user.password_hash.startswith("$2")


def test_get_current_user_rejects_missing_bearer_token(test_settings: Settings) -> None:
    with pytest.raises(AppError) as exc_info:
        get_current_user(credentials=None, token_issuer=JwtTokenIssuer(test_settings))

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "invalid_token"


def test_get_current_user_rejects_garbage_token(test_settings: Settings) -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-real-token")

    with pytest.raises(AppError) as exc_info:
        get_current_user(credentials=credentials, token_issuer=JwtTokenIssuer(test_settings))

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_expired_token(test_settings: Settings) -> None:
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": str(uuid.uuid4()),
        "name": "Fulano",
        "role": "COORDENACAO_PEDAGOGICA",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    token = jwt.encode(expired_payload, test_settings.jwt_secret, algorithm="HS256")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(AppError) as exc_info:
        get_current_user(credentials=credentials, token_issuer=JwtTokenIssuer(test_settings))

    assert exc_info.value.status_code == 401


def test_get_current_user_accepts_a_valid_token_without_a_db_round_trip(
    test_settings: Settings,
) -> None:
    user = User(
        id=uuid.uuid4(),
        name="Fulano de Tal",
        email="fulano@escola.test",
        password_hash="irrelevant-here",
        role=UserRole.COORDENACAO_PEDAGOGICA,
    )
    token = JwtTokenIssuer(test_settings).issue(user)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    current_user = get_current_user(credentials=credentials, token_issuer=JwtTokenIssuer(test_settings))

    assert current_user.id == str(user.id)
    assert current_user.name == user.name
    assert current_user.role == "COORDENACAO_PEDAGOGICA"


def test_users_table_enforces_unique_email_at_the_database_level(
    db_session: Session, seeded_user: UserModel
) -> None:
    from sqlalchemy.exc import IntegrityError

    duplicate = UserModel(
        name="Outra Pessoa",
        email=seeded_user.email,
        password_hash="$2b$12$abcdefghijklmnopqrstuv",
        role=UserRole.COORDENACAO_PEDAGOGICA,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    # The SAVEPOINT-joined session (see conftest.db_session) auto-restarts a
    # fresh savepoint once the failed one ends — no manual rollback needed,
    # and the test ends here regardless.
