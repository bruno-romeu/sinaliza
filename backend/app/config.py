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
    jwt_secret: str

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


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
