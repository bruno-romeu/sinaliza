# Sistema Inteligente de Apoio ao Acompanhamento da Trajetória Escolar

Sistema web para **identificar mudanças relevantes na trajetória escolar e apoiar o acompanhamento pedagógico de estudantes**, reunindo frequência, desempenho, atividades e registros qualitativos.

O projeto nasce do problema da evasão escolar, mas evita tratar o estudante como um “score de risco”.

A proposta é utilizar dados que já fazem parte da rotina escolar para responder:

> **Quais trajetórias apresentaram mudanças recentes que merecem ser analisadas pela equipe pedagógica, e quais evidências sustentam essa percepção?**

O sistema é um instrumento de **apoio à leitura da trajetória**, não um mecanismo automático de decisão.

---

## Problema

A evasão escolar raramente acontece de forma instantânea.

Antes de um eventual abandono podem existir mudanças como:

- redução progressiva da frequência;
- faltas consecutivas;
- queda de desempenho;
- aumento de atividades não entregues;
- mudanças na participação;
- dificuldades recorrentes registradas por professores;
- alterações relevantes em relação ao padrão anterior do próprio estudante.

Essas informações costumam estar distribuídas entre chamada, diário de classe, notas, atividades, planilhas e registros da coordenação.

O problema central não é apenas armazenar esses dados.

É **perceber mudanças ao longo do tempo e reunir contexto suficiente para que um profissional possa decidir se algum acompanhamento é necessário**.

---

## Objetivo

Construir um sistema capaz de:

1. consolidar informações acadêmicas e pedagógicas;
2. representar a trajetória escolar ao longo do tempo;
3. detectar mudanças e recorrências relevantes;
4. utilizar Machine Learning, de forma experimental, para estudar padrões associados à evasão;
5. organizar registros qualitativos em sinais estruturados;
6. apresentar evidências em vez de apenas classificações;
7. permitir acompanhamento e registro de ações da equipe;
8. apoiar a coordenação sem automatizar decisões sobre estudantes.

---

# Princípio de Produto

A interface não deve responder:

> Quem é o aluno de maior risco?

Ela deve ajudar a responder:

> O que mudou nesta trajetória e por que isso merece ser observado?

Evitar como elemento principal:

```text
Risco: 82%
ALTO RISCO
ranking de estudantes
top 10 alunos críticos
```

Preferir:

```text
Mudanças recentes

- frequência caiu progressivamente nas últimas 8 semanas;
- 3 de 5 atividades recentes não foram entregues;
- dois registros mencionam menor participação;
- existe acompanhamento aberto pela coordenação.
```

---

# Usuários

## Professor

Pode:

- registrar presença;
- registrar notas;
- registrar atividades entregues/não entregues;
- criar observações pedagógicas;
- visualizar a trajetória de estudantes sob sua responsabilidade;
- revisar sinais extraídos de seus registros.

O professor **não deve preencher manualmente um “nível de risco” ou “nível de engajamento”**.

## Coordenação Pedagógica

Pode:

- visualizar mudanças recentes;
- revisar evidências;
- abrir acompanhamentos;
- registrar ações realizadas;
- definir próximos passos;
- acompanhar evolução temporal;
- consultar histórico de registros.

---

# Dados do Sistema

## Frequência

Exemplos:

- presença;
- faltas;
- faltas consecutivas;
- percentual por período;
- tendência temporal.

## Desempenho

- notas;
- média por período;
- avaliações;
- mudanças de desempenho.

## Atividades

- entregue;
- não entregue;
- entregue parcialmente;
- prazo;
- disciplina.

## Histórico Escolar

Quando necessário ao experimento:

- série;
- retenções anteriores;
- reprovações;
- trajetória acadêmica anterior.

## Registros Pedagógicos

O professor registra fatos observáveis em texto livre.

Exemplo:

```text
Lucas participou menos das discussões nesta semana e não entregou
a última atividade. Nas primeiras semanas do semestre costumava
participar com frequência.
```

O sistema pode sugerir sinais estruturados:

```text
participation_change: negative
assignment_status: not_delivered
temporal_reference: recent
```

Esses sinais devem manter referência ao registro original e, quando usados em acompanhamento, passar por revisão humana.

---

# Papel da IA

Existem duas linhas possíveis de inteligência.

## 1. Machine Learning Tabular

O projeto pode utilizar Scikit-Learn para experimentar com padrões associados à evasão em dados tabulares.

Pipeline inicial:

```text
SimpleImputer
+
OneHotEncoder
+
StandardScaler quando aplicável
+
RandomForestClassifier
```

Outros modelos podem ser comparados posteriormente.

O resultado probabilístico do modelo é **artefato experimental**.

No MVP com dados sintéticos, ele não deve ser apresentado como uma probabilidade real de que um estudante irá abandonar a escola.

Evitar:

```text
Este estudante tem 82% de chance de evasão.
```

## 2. Processamento de Registros Pedagógicos

NLP/LLM pode ajudar a transformar observações livres em sinais estruturados.

```text
Registro original
      ↓
Extração
      ↓
Sinais sugeridos
      ↓
Revisão humana
      ↓
Sinais confirmados
```

A IA organiza informação. Ela não diagnostica o estudante.

---

# Visão Geral da Solução

```text
Dados acadêmicos
     │
     ├──── Frequência
     ├──── Notas
     ├──── Atividades
     └──── Histórico
     │
     ▼
Trajectory Processor
     │
     ├──── tendências
     ├──── mudanças de padrão
     └──── features temporais
     │
     ├───────────────┐
     ▼               ▼
ML Experimental   Registros Pedagógicos
     │               │
     │               ▼
     │          NLP / LLM
     │               │
     └──────┬────────┘
            ▼
        Evidence Layer
            │
            ▼
   Acompanhamento Pedagógico
            │
            ├──── trajetória
            ├──── evidências
            ├──── registros
            ├──── ações
            └──── próximos passos
```

---

# Dados Sintéticos

O MVP deve utilizar **dados sintéticos**.

Não é necessário acesso a dados reais para validar a arquitetura.

O dataset sintético deve ser controlado e documentado.

Perfis possíveis:

```text
estável
dificuldade acadêmica
queda de frequência
aumento de atividades pendentes
deterioração combinada
alta ausência com notas estáveis
mudança temporária seguida de recuperação
```

Sugestão inicial:

- aproximadamente 200 estudantes;
- um ano letivo;
- múltiplos períodos;
- observações qualitativas sintéticas;
- ground truth dos padrões usados na geração.

Os resultados obtidos nesse dataset não devem ser descritos como desempenho real em escolas.

## Preparar uma demonstração

Com o backend configurado (`backend/.env`), na pasta `backend`:

```bash
uv run python -m app.infrastructure.db.seed_dev_user
uv run python -m app.infrastructure.db.seed_dev_fixtures
uv run python -m app.synthetic.generate --seed 42 --reset
SINALIZA_DEMO_AS_OF=2026-09-25 uv run python -m app.synthetic.prepare_demo
```

Inicie o backend com o mesmo `SINALIZA_DEMO_AS_OF=2026-09-25`. Essa data é o fim do 3º bimestre, quando as notas e observações do bimestre já existem. O `prepare_demo` calcula uma vez a trajetória de cada estudante da demo, porque a página inicial só lista mudanças já calculadas. É uma ação manual, nunca agendada.

---

# Pipeline de Machine Learning

```text
Dataset sintético
      │
      ▼
Feature Engineering Temporal
      │
      ▼
Pré-processamento
      │
      ├── SimpleImputer
      ├── OneHotEncoder
      └── StandardScaler quando necessário
      │
      ▼
Train / Validation / Test
      │
      ▼
Modelo
      │
      ▼
Evaluation
      │
      ▼
Artifact Version
```

O mesmo pipeline de transformação deve ser utilizado no treinamento e na inferência.

---

# Features Temporais

O projeto deve priorizar trajetória, não apenas snapshot.

Exemplos:

```text
attendance_current
attendance_last_30_days
attendance_trend

grade_average_current
grade_average_previous_period
grade_trend

missing_assignments_current
missing_assignments_last_period
missing_assignment_delta
```

Um valor isolado é menos informativo do que sua mudança.

---

# Avaliação do ML

Não utilizar apenas Accuracy.

Métricas possíveis:

- Recall;
- Precision;
- F1;
- ROC-AUC;
- PR-AUC;
- matriz de confusão.

Como o dataset é sintético, a documentação deve separar:

> **capacidade de identificar os padrões simulados**

de:

> **validade preditiva em uma população escolar real**

O projeto só pode afirmar a primeira.

---

# Avaliação do NLP

Se houver extração de sinais de texto, criar observações sintéticas rotuladas.

Exemplo:

```text
texto
expected_signals
predicted_signals
```

Medir:

- Precision;
- Recall;
- F1 por categoria de sinal.

---

# Camada de Evidência

Qualquer sinal exibido deve apontar para sua fonte.

Exemplo:

```text
Mudança observada:
"menor participação"

Evidências:
- registro #184 — Matemática — 31/08
- registro #177 — Português — 29/08
```

Evitar:

```text
"A IA identificou risco alto."
```

---

# Acompanhamento

A unidade operacional é um **acompanhamento**, não um score.

Estados possíveis:

```text
EM_OBSERVACAO
ACOMPANHAMENTO_ATIVO
AGUARDANDO_RETORNO
ENCERRADO
```

Um acompanhamento pode conter:

- motivo;
- evidências;
- registros relacionados;
- ações;
- responsável;
- próximo passo;
- data de revisão.

---

# Interface

## Página Inicial

Mostrar:

- mudanças recentes;
- acompanhamentos em andamento;
- registros pedagógicos recentes;
- acompanhamentos sem atualização.

Evitar KPIs de “alunos de alto risco”.

## Trajetória do Estudante

Mostrar:

- resumo recente;
- frequência;
- desempenho;
- atividades;
- linha do tempo;
- registros;
- evidências;
- ações;
- próximos passos.

## Registros

A interface deve orientar:

> Registre fatos observáveis, evitando diagnósticos e rótulos.

## Acompanhamentos

Mostrar processo e próximos passos da equipe.

Não ordenar automaticamente estudantes por um score probabilístico.

---

# Modelo de Domínio Inicial

```text
User
Role

Student
Classroom
Enrollment
AcademicPeriod

AttendanceRecord
Assessment
Grade
Assignment
AssignmentSubmission

PedagogicalObservation
ExtractedSignal
SignalReview

TrajectorySnapshot
TrajectoryChange

FollowUp
FollowUpEvidence
FollowUpAction

MLModelVersion
MLPrediction
```

`MLPrediction` é resultado experimental, não um fato sobre o estudante.

---

# API Inicial

Exemplos conceituais:

```text
GET  /students
GET  /students/{id}
GET  /students/{id}/trajectory

POST /attendance
POST /grades
POST /assignments/{id}/submissions

POST /observations
GET  /observations/{id}/signals
POST /signals/{id}/review

GET  /trajectory/changes

POST /follow-ups
POST /follow-ups/{id}/actions
PATCH /follow-ups/{id}

GET  /ml/models
POST /ml/predictions
```

---

# Stack Sugerida

## Frontend
- React ou Next.js;
- TypeScript.

## Backend
- Python;
- FastAPI;
- Pydantic;
- SQLAlchemy/SQLModel.

## Banco
- PostgreSQL.

## Machine Learning
- Python;
- Pandas;
- NumPy;
- Scikit-Learn;
- Joblib.

## NLP / IA
Opcional no MVP inicial, sempre atrás de um adapter de provider.

## Infra
- Docker;
- Git;
- GitHub.

---

# Estrutura Sugerida

```text
school-trajectory/
│
├── AGENTS.md
├── README.md
│
├── apps/
│   ├── web/
│   └── api/
│
├── ml/
│   ├── datasets/
│   ├── features/
│   ├── training/
│   ├── evaluation/
│   └── artifacts/
│
├── data/
│   ├── synthetic/
│   └── fixtures/
│
├── tests/
│
├── docs/
│   ├── architecture.md
│   ├── data-model.md
│   ├── model-evaluation.md
│   └── decisions/
│
└── docker-compose.yml
```

---

# Escopo do MVP

## Obrigatório

- estudantes e turmas fictícias;
- dados acadêmicos sintéticos;
- frequência;
- notas;
- atividades;
- trajetória temporal;
- detecção de mudanças;
- registros pedagógicos;
- acompanhamento;
- pipeline ML experimental;
- avaliação do modelo;
- interface de trajetória;
- persistência;
- testes.

## Desejável

- extração NLP/LLM de sinais;
- revisão humana;
- comparação entre algoritmos;
- explicabilidade básica do modelo.

## Fora do MVP

- integração com secretaria de educação;
- dados reais;
- tomada automática de decisão;
- comunicação automática com responsáveis;
- recomendação disciplinar;
- diagnóstico psicológico;
- implantação em escola real;
- uso do modelo em decisão de alto impacto.

---

# Princípios Éticos e de UX

## 1. Não determinar o futuro do estudante

Nunca afirmar:

```text
"O estudante irá evadir."
```

## 2. Não apresentar probabilidade sintética como realidade

Nunca:

```text
"82% de chance de evasão"
```

quando o modelo foi treinado em dados simulados.

## 3. Evidência antes de rótulo

Mostrar mudanças observáveis.

## 4. Humano no processo

```text
detecção
↓
organização de evidências
↓
análise pedagógica
↓
ação humana
```

## 5. Não transformar estudante em ativo

Evitar linguagem de ranking, performance ou score do aluno quando houver alternativa pedagógica.

---

# Privacidade

Em ambiente real, dados educacionais exigiriam autenticação, autorização, minimização, auditoria, retenção adequada e conformidade com a LGPD.

No TCC:

> utilizar dados sintéticos por padrão.

Nunca incluir dados reais de estudantes em fixtures ou commits.

---

# Execução com Docker

O sistema é empacotado em três serviços (`postgres`, `backend`, `frontend`) descritos em `docker-compose.yml`, na raiz do repositório.

Para rodar localmente ou em uma VM:

```bash
cp backend/.env.example .env   # .env na raiz — o Compose carrega esse arquivo automaticamente
docker compose up --build
```

O `frontend` (Nginx) fica disponível em `http://localhost/` e faz proxy de `/api/*` para o `backend`. Dados do Postgres persistem em um volume nomeado entre reinicializações.

Para atualizar uma instância já publicada:

```bash
git pull
docker compose up --build
```

---

# Roadmap

## Etapa 1 — Domínio e Dados
Schema, turmas, estudantes, frequência, notas, atividades e dataset sintético.

## Etapa 2 — Trajetória
Snapshots temporais, tendências, mudanças e linha do tempo.

## Etapa 3 — Acompanhamento
Registros pedagógicos, follow-ups, ações e evidências.

## Etapa 4 — ML
Feature engineering, pipeline, treinamento, avaliação e versionamento.

## Etapa 5 — NLP
Se houver tempo: extração de sinais, revisão humana e métricas.

## Etapa 6 — Interface
Central de acompanhamento, trajetória individual, registros e follow-ups.

## Etapa 7 — Validação
Testes, métricas, limitações e demonstração.

---

# Resultado Esperado

Ao final, o sistema deve demonstrar:

```text
dados escolares
→ trajetória
→ detecção de mudanças
→ evidências
→ acompanhamento humano
```

e, de forma experimental:

```text
dados sintéticos
→ Machine Learning
→ avaliação de padrões
```

O objetivo não é prever com certeza quem abandonará a escola.

O objetivo é demonstrar como dados distribuídos da rotina escolar podem ser organizados e analisados para **dar visibilidade antecipada a mudanças que merecem acompanhamento pedagógico**.
