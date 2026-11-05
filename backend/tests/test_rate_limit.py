"""Rate limiting de `POST /auth/login` (app/presentation/rate_limit.py).

Cada teste constrói seu próprio app via `create_app(settings=...)` com
limites baixos, em vez de depender do app global da suíte — assim o
limitador é exercitado de verdade (e não "passa" por estar desligado), sem
que esses limites baixos contaminem os outros 423 testes.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.infrastructure.db.base import get_db
from app.infrastructure.db.models import UserModel
from app.main import create_app
from app.presentation.rate_limit import _SlidingWindowCounter

RATE_LIMITED_BODY = {
    "error": {
        "code": "rate_limited",
        "message": "Muitas tentativas de login. Aguarde alguns instantes e tente novamente.",
    }
}


def _settings(base: Settings, **overrides) -> Settings:
    return Settings(
        database_url=base.database_url,
        jwt_secret=base.jwt_secret,
        jwt_expire_minutes=base.jwt_expire_minutes,
        **overrides,
    )


@pytest.fixture()
def make_client(db_session: Session, test_settings: Settings):
    """Fábrica de `TestClient` sobre um app novo com limites próprios."""
    clients: list[TestClient] = []

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def factory(**overrides) -> TestClient:
        settings = _settings(test_settings, **overrides)
        app = create_app(settings=settings)
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_settings] = lambda: settings
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield factory

    for client in clients:
        client.__exit__(None, None, None)


def _login(client: TestClient, email: str, password: str = "senha-errada", **kwargs):
    return client.post("/auth/login", json={"email": email, "password": password}, **kwargs)


def test_login_is_blocked_with_429_after_the_configured_number_of_attempts(
    make_client, seeded_user: UserModel
) -> None:
    client = make_client(rate_limit_login_max_attempts=3, rate_limit_login_window_seconds=300)

    for _ in range(3):
        assert _login(client, seeded_user.email).status_code == 401

    blocked = _login(client, seeded_user.email)

    assert blocked.status_code == 429
    assert blocked.json() == RATE_LIMITED_BODY
    retry_after = int(blocked.headers["Retry-After"])
    assert 0 < retry_after <= 300


def test_successful_logins_consume_the_same_budget(make_client, seeded_user: UserModel) -> None:
    """A contagem acontece antes do despacho, então independe do resultado —
    é o que impede o limitador de reagir de forma diferente a conta
    existente e inexistente."""
    client = make_client(rate_limit_login_max_attempts=2)

    assert _login(client, seeded_user.email, "Senha-Correta-123").status_code == 200
    assert _login(client, seeded_user.email, "Senha-Correta-123").status_code == 200
    assert _login(client, seeded_user.email, "Senha-Correta-123").status_code == 429


def test_limit_does_not_leak_whether_an_account_exists(make_client, seeded_user: UserModel) -> None:
    """Armadilha de enumeração: a chave é o cliente, nunca o e-mail. Tentar
    com e-mail desconhecido gasta a mesma cota que o conhecido, e a resposta
    de bloqueio é idêntica nos dois casos."""
    known = make_client(rate_limit_login_max_attempts=2)
    assert _login(known, seeded_user.email).status_code == 401
    assert _login(known, "nao-existe@escola.test").status_code == 401
    known_blocked = _login(known, seeded_user.email)

    unknown = make_client(rate_limit_login_max_attempts=2)
    assert _login(unknown, "nao-existe@escola.test").status_code == 401
    assert _login(unknown, "tambem-nao-existe@escola.test").status_code == 401
    unknown_blocked = _login(unknown, "nao-existe@escola.test")

    # Terceira tentativa bloqueada nos dois cenários: a cota é consumida por
    # e-mails conhecidos e desconhecidos exatamente do mesmo jeito.
    assert known_blocked.status_code == unknown_blocked.status_code == 429
    assert known_blocked.json() == unknown_blocked.json()
    remaining_header = "RateLimit-Remaining"
    assert known_blocked.headers[remaining_header] == unknown_blocked.headers[remaining_header]


def test_allowed_responses_carry_the_ratelimit_headers(make_client, seeded_user: UserModel) -> None:
    client = make_client(rate_limit_login_max_attempts=3, rate_limit_login_window_seconds=120)

    first = _login(client, seeded_user.email)

    assert first.headers["RateLimit-Limit"] == "3"
    assert first.headers["RateLimit-Remaining"] == "2"
    assert 0 < int(first.headers["RateLimit-Reset"]) <= 120
    assert "Retry-After" not in first.headers

    assert _login(client, seeded_user.email).headers["RateLimit-Remaining"] == "1"


def test_counting_uses_the_rightmost_forwarded_for_entry(
    make_client, seeded_user: UserModel
) -> None:
    """O Nginx acrescenta o IP real ao final de X-Forwarded-For, então só a
    entrada mais à direita é confiável. Entradas forjadas à esquerda não
    podem render cota nova."""
    client = make_client(rate_limit_login_max_attempts=2, rate_limit_trusted_proxy_hops=1)

    forged_a = {"X-Forwarded-For": "1.2.3.4, 203.0.113.10"}
    forged_b = {"X-Forwarded-For": "9.9.9.9, 203.0.113.10"}

    assert _login(client, seeded_user.email, headers=forged_a).status_code == 401
    assert _login(client, seeded_user.email, headers=forged_b).status_code == 401
    # Mesmo peer real (203.0.113.10): a cota é compartilhada apesar do
    # cabeçalho forjado ser diferente.
    assert _login(client, seeded_user.email, headers=forged_a).status_code == 429

    # Um peer real diferente tem cota própria.
    other_peer = {"X-Forwarded-For": "1.2.3.4, 203.0.113.11"}
    assert _login(client, seeded_user.email, headers=other_peer).status_code == 401


def test_forwarded_for_is_ignored_when_no_proxy_is_trusted(
    make_client, seeded_user: UserModel
) -> None:
    client = make_client(rate_limit_login_max_attempts=2, rate_limit_trusted_proxy_hops=0)

    for index in range(2):
        response = _login(
            client, seeded_user.email, headers={"X-Forwarded-For": f"203.0.113.{index}"}
        )
        assert response.status_code == 401

    # Trocar o cabeçalho não gera cota nova: vale o peer da conexão.
    blocked = _login(client, seeded_user.email, headers={"X-Forwarded-For": "203.0.113.99"})
    assert blocked.status_code == 429


def test_other_routes_are_not_rate_limited(make_client) -> None:
    """O limite cobre só a rota anônima. As demais exigem JWT e ficam fora
    dele de propósito — ver docstring de app/presentation/rate_limit.py."""
    client = make_client(rate_limit_login_max_attempts=2)

    for _ in range(6):
        response = client.get("/home")
        assert response.status_code != 429


def test_rate_limit_can_be_disabled(make_client, seeded_user: UserModel) -> None:
    client = make_client(rate_limit_enabled=False, rate_limit_login_max_attempts=1)

    for _ in range(5):
        assert _login(client, seeded_user.email).status_code == 401


def test_the_window_resets_when_the_application_starts(make_client, seeded_user: UserModel) -> None:
    """O contador vive na memória do processo e começa vazio a cada start
    (lifespan em app/main.py) — é também o que mantém os testes existentes
    isolados uns dos outros."""
    first = make_client(rate_limit_login_max_attempts=1)
    assert _login(first, seeded_user.email).status_code == 401
    assert _login(first, seeded_user.email).status_code == 429

    second = make_client(rate_limit_login_max_attempts=1)
    assert _login(second, seeded_user.email).status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"rate_limit_login_max_attempts": 0},
        {"rate_limit_login_max_attempts": -1},
        {"rate_limit_login_window_seconds": 0},
        {"rate_limit_trusted_proxy_hops": -1},
    ],
)
def test_invalid_rate_limit_configuration_fails_fast(
    test_settings: Settings, overrides: dict
) -> None:
    with pytest.raises(ValidationError):
        _settings(test_settings, **overrides)


def test_zero_trusted_proxy_hops_is_a_valid_configuration(test_settings: Settings) -> None:
    settings = _settings(test_settings, rate_limit_trusted_proxy_hops=0)

    assert settings.rate_limit_trusted_proxy_hops == 0


def test_reset_never_exceeds_the_window_at_realistic_clock_values() -> None:
    """Fixa o invariante que o CI viu quebrado: `RateLimit-Reset` anunciou
    121 numa janela de 120s, de forma intermitente.

    Este teste NAO reproduz aquela falha -- a causa raiz nao foi
    identificada (ver o comentario em `rate_limit.hit`). Ele fixa a
    propriedade que importa para quem consome o cabecalho: o limitador
    nunca anuncia um tempo de reset maior que a janela que ele honra.

    Varre varios instantes em vez de confiar no relogio, para nao virar um
    teste que passa por sorte.
    """
    window = 120
    counter = _SlidingWindowCounter(max_events=3, window_seconds=window, max_keys=8)

    for step in range(2000):
        now = 1_700_000_000.0 + step * 0.4999
        decision = counter.hit(f"chave-{step}", now)
        assert 0 < decision.reset_seconds <= window, (
            f"reset_seconds={decision.reset_seconds} para now={now!r}"
        )
