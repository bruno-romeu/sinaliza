# Sinaliza

**Apoio ao acompanhamento da trajetória escolar.** O Sinaliza organiza presença, notas, entregas e observações pedagógicas, identifica mudanças relevantes na trajetória de cada estudante e mostra a evidência que sustenta cada uma — para que a coordenação decida o próximo passo.

[![CI](https://github.com/bruno-romeu/sinaliza/actions/workflows/ci.yml/badge.svg)](https://github.com/bruno-romeu/sinaliza/actions/workflows/ci.yml)

**Demonstração:** http://sinaliza.mexicocentral.cloudapp.azure.com

> Projeto acadêmico (TCC — Análise e Desenvolvimento de Sistemas, ULBRA). Todos os dados são **sintéticos**: nenhum estudante real.

## Princípio

Sistemas de alerta de evasão costumam reduzir o estudante a uma probabilidade ("82% de chance de evadir") e a um ranking de risco. O rótulo passa a determinar como o estudante é tratado.

O Sinaliza recusa isso por desenho. Em vez de perguntar *qual a chance deste aluno evadir*, pergunta *o que mudou recentemente na trajetória dele, e por que isso merece atenção*:

- não calcula nem exibe probabilidade de evasão;
- não ordena estudantes por risco;
- toda mudança exibida aponta para os registros que a sustentam;
- o acompanhamento é um processo conduzido por pessoas, não um estado atribuído pelo sistema.

As regras que governam o projeto estão em [`AGENTS.md`](AGENTS.md).

## Funcionalidades

- **Lançamentos** — presença por turma e data, notas por disciplina e período, atividades e status de entrega, observações pedagógicas em texto livre.
- **Trajetória** — indicadores calculados em janela de tempo, com gráfico por período e a faixa habitual do próprio estudante.
- **Detecção de mudanças** — uma mudança só é sinalizada quando sinais de eixos diferentes convergem, o que reduz o ruído de um período atípico isolado.
- **Evidências** — cada mudança lista os registros de presença, nota, entrega e observação que a originaram.
- **Acompanhamento** — abertura vinculada à evidência, registro de ações e ciclo de status (`em observação`, `ativo`, `aguardando retorno`, `encerrado`).
- **Machine Learning experimental** — pipeline de classificação treinado sobre o dataset sintético, mantido fora da interface. Ver [Machine Learning](#machine-learning).

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12, FastAPI 0.141, SQLAlchemy 2, Alembic 1.20, Pydantic Settings 2.15 |
| Banco | PostgreSQL 16 |
| Frontend | React 19.3, TypeScript 5.9, Vite 8.3, React Router 7 |
| ML | scikit-learn 1.9 |
| Testes | pytest, Vitest 5, Testing Library, Playwright |
| Infra | Docker Compose, Nginx 1.27, GitHub Actions |

## Como executar

Requer Docker com Compose.

```sh
git clone https://github.com/bruno-romeu/sinaliza.git
cd sinaliza
cp backend/.env.example .env
```

Edite o `.env` e defina um `JWT_SECRET` com **no mínimo 32 caracteres** — o backend não sobe sem isso:

```sh
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Suba a stack. O backend aplica as migrations automaticamente:

```sh
docker compose up -d --build
```

Popule o banco. A ordem importa:

```sh
docker compose exec backend python -m app.infrastructure.db.seed_dev_user     # usuário de acesso
docker compose exec backend python -m app.infrastructure.db.seed_dev_fixtures # períodos letivos
docker compose exec backend python -m app.synthetic.generate --seed 42 --students 200 --reset
docker compose exec backend python -m app.synthetic.prepare_demo              # calcula as mudanças
```

O último passo é necessário porque as mudanças de trajetória são calculadas quando a trajetória é lida; sem ele, a página inicial começa vazia.

Acesse http://localhost com `DEV_SEED_EMAIL` e `DEV_SEED_PASSWORD` do `.env`.

## Desenvolvimento

### Testes do backend

Os testes usam um PostgreSQL separado, na porta 5433:

```sh
docker run -d --name sinaliza-test-postgres -p 5433:5432 \
  -e POSTGRES_USER=sinaliza -e POSTGRES_PASSWORD=sinaliza -e POSTGRES_DB=sinaliza_test \
  postgres:16-alpine

cd backend
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

### Frontend

Com a stack do Compose rodando, o servidor de desenvolvimento usa o backend dela:

```sh
cd frontend
npm ci
VITE_API_PROXY_TARGET=http://localhost VITE_API_PROXY_KEEP_PREFIX=true npm run dev
```

Os tipos da API são gerados a partir do OpenAPI do backend:

```sh
(cd ../backend && uv run python -m app.export_openapi)
npm run generate:api-types
```

```sh
npm test                 # Vitest
npm run lint             # ESLint
npm run test:e2e         # Playwright, contra a stack em http://localhost
```

## Machine Learning

O modelo é **experimental**. Ele avalia se um pipeline consegue distinguir os perfis de trajetória construídos no dataset sintético — não mede capacidade de prever evasão real. O score nunca é exibido na interface.

```sh
docker compose exec backend python -m app.ml.compare    # compara modelos candidatos
docker compose exec backend python -m app.ml.train      # treina e registra uma versão
docker compose exec backend python -m app.ml.evaluate   # avalia e persiste as métricas
```

Metodologia, resultados e limites estão em [`docs/model-evaluation.md`](docs/model-evaluation.md).

## Estrutura

```
backend/
  app/
    domain/          regras de negócio puras (trajetória, convergência, acompanhamento)
    application/     casos de uso
    infrastructure/  persistência (SQLAlchemy) e segurança
    presentation/    API HTTP (FastAPI)
    synthetic/       gerador determinístico do dataset sintético
    ml/              pipeline experimental, executado fora da API
  alembic/           migrations
  tests/
frontend/
  src/
    pages/           telas
    components/      componentes de interface
    api/             cliente HTTP e tipos gerados
  e2e/               testes Playwright
deploy/azure/        publicação na Azure
docs/                documentação técnica
```

## Documentação

| Documento | Conteúdo |
|---|---|
| [`docs/prd.md`](docs/prd.md) | requisitos funcionais e não funcionais (RF/RNF) |
| [`docs/architecture.md`](docs/architecture.md) | decisões de arquitetura (AD-1 a AD-12) |
| [`docs/data-model.md`](docs/data-model.md) | modelo de dados |
| [`docs/model-evaluation.md`](docs/model-evaluation.md) | avaliação do Machine Learning e seus limites |
| [`docs/decisions/`](docs/decisions) | registros de decisão |
| [`deploy/azure/README.md`](deploy/azure/README.md) | publicação |

Comentários no código citam identificadores de requisito (`RF-`, `RNF-`) e de arquitetura (`AD-`), definidos nos documentos acima. Referências a especificações por história (`spec-*`) apontam para documentos de desenvolvimento preservados no histórico do repositório.

## Dados

O dataset é gerado de forma determinística a partir de uma seed. As taxas de abandono, evasão e reprovação são calibradas pelo Censo Escolar 2023 (INEP); os parâmetros sem fonte pública são declarados como suposições de projeto. Cada parâmetro registra sua fonte e seu nível de confiança em [`backend/app/synthetic/calibration.py`](backend/app/synthetic/calibration.py).

Nenhum dado real de estudante é usado ou versionado.
