# syntax=docker/dockerfile:1
#
# spec-6-1: closes epic-1-retro-item-9 — neither `backend/openapi.json` nor
# `frontend/src/api/schema.d.ts` is committed to git (.gitignore), so the
# image build must generate both itself from a fresh clone, unaided.
#
# Build context MUST be the repo root (see docker-compose.yml) so this stage
# can see `backend/` alongside `frontend/`.

# ---- stage 1: generate openapi.json from the backend source ----
# Build-time only: installs the backend's Python deps and imports app.main
# purely to call app.openapi() and dump JSON. Never starts a server, never
# touches a real database (create_engine is lazy) — dummy env vars suffice.
FROM python:3.12-slim AS openapi
RUN pip install --no-cache-dir uv
WORKDIR /backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/app ./app
ENV DATABASE_URL=postgresql+psycopg://dummy:dummy@localhost:5432/dummy \
    JWT_SECRET=dummy-build-time-secret-never-used-anywhere
RUN uv run python -m app.export_openapi

# ---- stage 2: generate typed API client, build the Vite SPA ----
FROM node:24-slim AS build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY --from=openapi /backend/openapi.json ../backend/openapi.json
RUN npm run generate:api-types && npm run build

# ---- stage 3: serve the static build with Nginx, reverse-proxying /api ----
#
# Sem `USER` aqui, de propósito (deferred-work, spec-6-1). Na imagem oficial
# do Nginx o master roda como root por desenho — precisa disso para o bind na
# 80 e para preparar /var/cache/nginx e o pid — e já baixa privilégio nos
# workers, que rodam como `nginx` e são quem de fato atende requisição
# (confirmado em execução). Forçar `USER nginx` exigiria mudar a porta de
# escuta, remapear a publicação no compose e contornar o entrypoint da
# imagem: mais superfície alterada do que privilégio removido, já que o
# processo exposto ao tráfego não é o root. O backend, que é imagem nossa e
# escuta em porta alta, passou a rodar como não-root (backend/Dockerfile).
FROM nginx:1.27-alpine AS runtime
COPY --from=build /frontend/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
