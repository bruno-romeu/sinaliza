# syntax=docker/dockerfile:1
#
# spec-6-1: backend image — install deps with uv, run Alembic migrations,
# then serve with a single Uvicorn worker (AD-3: the ML artifact singleton
# is in-memory and not safe to share across multiple worker processes).

# Build context is the repo root (see docker-compose.yml), not backend/ —
# so every COPY below is prefixed with backend/.

# ---- deps stage: resolve and install Python dependencies with uv ----
FROM python:3.12-slim AS deps
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# ---- runtime stage ----
FROM python:3.12-slim AS runtime
WORKDIR /app

COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x ./docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
