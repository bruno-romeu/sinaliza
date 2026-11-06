"""Application configuration.

All configuration is read from environment variables (optionally via a local
`.env` file for development) — never hardcoded secrets in source. See
`.env.example` for the full list of variables this app understands.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Required — no defaults, so a missing value fails fast at startup rather
    # than silently running with an insecure/incorrect configuration.
    database_url: str

    # HS256 assina com o segredo cru, então o segredo *é* a chave HMAC. O
    # próprio PyJWT 2.15 avisa (`InsecureKeyLengthWarning`, RFC 7518 §3.2) ao
    # assinar com menos de 32 bytes; `min_length=32` transforma esse aviso em
    # falha no start — quando ainda dá para corrigir — em vez de um app no ar
    # emitindo tokens com chave fraca.
    jwt_secret: str = Field(min_length=32)

    # gt=0 so a misconfigured 0/negative value fails fast instead of quietly
    # issuing tokens that are already expired the moment they're minted.
    jwt_expire_minutes: int = Field(default=60, gt=0)

    # Dev-only seed configuration for `app.infrastructure.db.seed_dev_user`.
    # Left unset in any environment that isn't seeding a dev/demo user.
    dev_seed_name: str = "Coordenação Pedagógica"
    dev_seed_email: str | None = None
    dev_seed_password: str | None = None

    # Default rolling-window size (days) for `GET /students/{id}/trajectory`
    # (spec Code Map) — overridable per-request via `?window_days=`.
    # `gt=0` so a misconfigured 0/negative value fails fast rather than
    # silently producing an empty or inverted window. `le=3650` (10 years)
    # caps it so `date - timedelta(days=2*window_days)` can never overflow
    # `datetime.date`'s range and raise an unhandled `OverflowError`.
    trajectory_window_days: int = Field(default=30, gt=0, le=3650)

    # Rate limiting de `POST /auth/login` (app.presentation.rate_limit) — a
    # única rota anônima do sistema. Desligável (`RATE_LIMIT_ENABLED=false`)
    # para diagnóstico/demonstração; os testes do limitador constroem o app
    # com seus próprios valores em vez de depender do ambiente.
    rate_limit_enabled: bool = True

    # 10 tentativas por cliente a cada 5 minutos. O número vem do uso real:
    # há uma única conta semeada, operada por uma pessoa, que erra a senha
    # poucas vezes — 2/min é folgado para isso e inútil para adivinhação
    # (120 tentativas/hora contra um espaço de senhas). `gt=0` para falhar
    # cedo: 0 bloquearia todo login, inclusive o legítimo.
    rate_limit_login_max_attempts: int = Field(default=10, gt=0)
    rate_limit_login_window_seconds: int = Field(default=300, gt=0)

    # Quantos proxies confiáveis existem à frente do backend. 1 = o Nginx do
    # docker-compose. `ge=0` (e não `gt=0`) porque 0 é um valor válido e
    # significativo: ignorar `X-Forwarded-For` por completo, para um backend
    # exposto diretamente. Ver `app.presentation.rate_limit.client_key`.
    rate_limit_trusted_proxy_hops: int = Field(default=1, ge=0)

    # Onde `python -m app.ml.train` (spec-5-1) escreve os `Pipeline`
    # serializados. Offline-only — nunca lido pelo processo web nem por
    # `Depends` do FastAPI (AD-3).
    #
    # Quem *lê* o artefato (`predict.py`, `evaluate.py`) não passa por aqui:
    # carrega o `artifact_path` gravado na própria linha `MLModelVersion`. O
    # comentário anterior prometia o contrário ("Story 5.2's live-inference
    # loader will read this same setting"), e era por causa dessa promessa que
    # `run_prediction` carregava um `artifact_dir` que nunca lia — parâmetro
    # removido na onda de higiene. Esta é, portanto, a configuração do
    # **treino**, e só dele.
    ml_artifact_dir: str = "./ml_artifacts"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
