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

# deferred-work (spec-6-1): o processo não precisa de root. Ele escuta na
# 8000 (porta alta, não privilegiada), não instala nada em runtime e só
# escreve em `ml_artifact_dir` — criado aqui já pertencente ao usuário para
# que `docker compose exec backend python -m app.ml.train` continue
# funcionando. O código em /app fica pertencendo ao root e apenas legível
# pelo `app`: um comprometimento do processo não reescreve a própria
# aplicação. Isto é defesa em profundidade, não a fronteira de segurança —
# a fronteira é o Nginx não publicar esta porta (ver docker-compose.yml).
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/ml_artifacts \
    && chown app:app /app/ml_artifacts
USER app

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
