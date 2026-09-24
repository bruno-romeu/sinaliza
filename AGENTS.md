# AGENTS.md

Instruções globais para agentes de IA que trabalham no projeto **Sistema Inteligente de Apoio ao Acompanhamento da Trajetória Escolar**.

Leia `README.md` antes de modificar código.

## Missão

Construir um sistema acadêmico que organize dados escolares, identifique mudanças de trajetória e forneça evidências para acompanhamento pedagógico.

A origem do problema é a evasão escolar, mas o produto **não deve rotular ou determinar o futuro de estudantes**.

Fluxo principal:

```text
dados acadêmicos
→ trajetória temporal
→ mudanças
→ evidências
→ acompanhamento
→ decisão humana
```

Fluxo experimental de ML:

```text
dados sintéticos
→ features
→ modelo
→ métricas
→ resultado experimental
```

## Regra mais importante

Nunca transformar a saída do sistema em uma afirmação determinística ou pseudo-determinística sobre o estudante.

Proibido como comportamento padrão:

```text
"82% de chance de evasão"
"aluno de alto risco"
"este aluno irá abandonar"
"ranking dos alunos mais críticos"
```

Preferir:

```text
"mudanças recentes na trajetória"
"sinais observados"
"evidências"
"acompanhamento"
"revisão pedagógica"
```

## Limites do MVP

Assumir:

- dados sintéticos;
- aproximadamente 200 estudantes fictícios;
- um ano letivo;
- PostgreSQL;
- frontend React/Next.js;
- backend FastAPI;
- Scikit-Learn;
- nenhuma integração real com sistemas educacionais;
- nenhuma tomada de decisão automatizada.

Não adicionar dados reais.

## Separação de responsabilidades

### Dados acadêmicos

São fatos registrados:

- presença;
- falta;
- nota;
- atividade entregue;
- atividade não entregue.

### Trajetória

É computada a partir da evolução temporal desses fatos.

### Registros pedagógicos

São observações humanas.

### Sinais extraídos

São interpretações estruturadas que devem apontar para sua evidência.

### Acompanhamento

É processo e decisão humana.

### ML Prediction

É resultado experimental.

Não misturar esses conceitos.

## UX

A interface deve se comportar como ferramenta pedagógica.

Não como:

- CRM;
- painel financeiro;
- asset management;
- ranking competitivo.

Priorizar:

- linha do tempo;
- mudança;
- contexto;
- registro;
- próximo passo.

## Professor

Não exigir que o professor preencha manualmente:

```text
risk_score
engagement_score
student_priority
```

O professor registra ações naturais da rotina:

- chamada;
- avaliação;
- entrega;
- observação.

## Observações pedagógicas

Solicitar fatos observáveis.

Bom:

```text
"Participou menos das discussões nas últimas duas aulas e não
entregou a atividade desta semana."
```

Evitar induzir:

```text
"Está desmotivado."
"É aluno de risco."
"Provavelmente irá evadir."
```

## NLP / LLM

Se implementado:

```text
observation
→ extraction
→ suggested signals
→ human review
→ confirmed signals
```

Todo `ExtractedSignal` deve manter:

```text
source_observation_id
signal_type
value
provider/model
review_status
```

Nunca descartar a fonte original.

Sinal extraído automaticamente não deve virar fato confirmado sem revisão quando for usado em acompanhamento.

## Machine Learning

O ML é experimental.

Objetivo:

> avaliar se um pipeline consegue distinguir padrões simulados construídos no dataset.

Não afirmar validade real.

### Pipeline

Preferir um pipeline único do Scikit-Learn:

```text
preprocessing
+
model
```

Evitar preprocessing duplicado entre treino e inferência.

### Modelos

Começar simples.

Exemplo:

```text
LogisticRegression
RandomForestClassifier
```

Comparar antes de adicionar modelos complexos.

Não adicionar XGBoost/LightGBM apenas para parecer mais avançado.

## Score de modelo

Se `predict_proba()` for utilizado, persistir como dado experimental.

Exemplo interno:

```text
model_score = 0.82
```

Não exibir automaticamente como:

```text
82% de chance de evasão
```

No produto, preferir evidências e mudanças.

## Features

Priorizar features temporais.

Bom:

```text
attendance_trend
grade_delta
missing_assignment_delta
consecutive_absences
```

Menos interessante isoladamente:

```text
attendance_current
grade_current
```

Nunca introduzir feature sensível sem necessidade e justificativa.

## Dados sintéticos

O gerador deve ser:

- determinístico com seed;
- documentado;
- testável;
- reproduzível.

Cada perfil sintético deve possuir regra conhecida.

Exemplo:

```text
profile = falling_attendance
```

Não depender de geração aleatória opaca.

Persistir metadados da geração.

Nunca misturar dataset sintético com dados reais.

## Avaliação de ML

Implementar:

- Precision;
- Recall;
- F1;
- matriz de confusão.

ROC-AUC/PR-AUC podem ser adicionadas.

Resultados devem ser apresentados como:

> desempenho sobre o dataset sintético utilizado.

Não:

> precisão do sistema em prever evasão escolar no mundo real.

## Avaliação de NLP

Quando houver NLP, usar conjunto rotulado.

Implementar por categoria:

- Precision;
- Recall;
- F1.

Exigir exemplos e labels versionados.

## Evidência

Toda mudança exibida deve poder apontar para dado-fonte.

Exemplo:

```text
TrajectoryChange
type: ATTENDANCE_DROP
period: last_8_weeks
source_records: [...]
```

Evitar:

```text
reason = "AI detected"
```

## Acompanhamento

Entidade `FollowUp` representa um processo humano.

Estados possíveis:

```text
EM_OBSERVACAO
ACOMPANHAMENTO_ATIVO
AGUARDANDO_RETORNO
ENCERRADO
```

Não criar estado:

```text
HIGH_RISK
```

como substituto de acompanhamento.

## Banco de dados

Usar migrations.

Entidades previstas:

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

Evitar misturar resultados de modelo com fatos escolares.

## API

Controllers finos.

Fluxo:

```text
request
→ validation
→ application service
→ domain/repository
→ response
```

Não colocar feature engineering dentro de endpoint HTTP.

Não carregar artefato ML a cada request.

## Versionamento de modelo

Persistir ao menos:

```text
model_version
training_dataset_version
feature_schema_version
metrics
artifact_path
created_at
```

Prediction deve apontar para a versão usada.

## Privacidade

No TCC:

> dados reais são proibidos por padrão.

Nunca commitar:

- nome real de estudante;
- matrícula real;
- telefone;
- endereço;
- observação real;
- dado de saúde;
- informação familiar real.

Fixtures devem usar identidades fictícias.

## Segurança futura

Se houver autenticação:

- controle por papel;
- least privilege;
- auditoria;
- não expor todas as turmas a professores sem necessidade.

Não implementar security theater se autenticação ainda estiver fora do milestone atual.

## Frontend

### Central

Mostrar:

- mudanças recentes;
- acompanhamentos;
- registros;
- próximos passos.

Evitar:

```text
KPI: 38 alunos de alto risco
ranking
heatmap de risco
```

### Estudante

Mostrar:

- trajetória;
- fatos;
- linha do tempo;
- registros;
- evidências;
- ações.

### Explicações

Texto gerado por IA nunca substitui dado-fonte.

## Gráficos

Usar visualização temporal quando ela ajuda a perceber mudança.

Não transformar toda métrica em gráfico.

Não usar cor vermelha como mecanismo único para classificar estudantes.

Considerar acessibilidade.

## Testes

### Unitários

- gerador sintético;
- feature engineering;
- tendência;
- detecção de mudança;
- métricas;
- preprocessing.

### Integração

- persistência;
- API;
- inferência;
- follow-up.

### ML

Testar:

- schema;
- pipeline serializado;
- compatibilidade de inferência;
- reproducibilidade.

### NLP

Testar parsing de outputs estruturados e fluxo de revisão.

## Ordem de implementação

Preferir:

1. domínio escolar;
2. dataset sintético;
3. persistência;
4. frequência/notas/atividades;
5. trajetória temporal;
6. detecção de mudanças;
7. registros pedagógicos;
8. acompanhamento;
9. frontend de trajetória;
10. ML experimental;
11. avaliação;
12. NLP/LLM;
13. refinamento visual.

Não começar pela IA.

## Controle de escopo

Antes de implementar:

1. Isso melhora a compreensão da trajetória?
2. É útil para acompanhamento?
3. É necessário para o MVP?
4. Consegue ser demonstrado com dados sintéticos?
5. É seguro e explicável?

Se a resposta for majoritariamente não, provavelmente está fora do escopo.

## Atalhos proibidos

Não:

- usar dados reais;
- inventar validação escolar real;
- dizer que dados sintéticos provam eficácia pedagógica real;
- chamar score de “probabilidade real”;
- gerar ranking de estudantes;
- automatizar intervenção;
- criar recomendação disciplinar;
- inferir diagnóstico;
- usar LLM como única fonte de evidência;
- esconder a origem de um sinal;
- treinar e avaliar no mesmo conjunto;
- escolher modelo apenas por Accuracy;
- adicionar tecnologia sem necessidade.

## Documentação

Atualizar:

```text
README.md
docs/architecture.md
docs/data-model.md
docs/model-evaluation.md
docs/decisions/
```

Registrar decisões importantes sobre:

- features utilizadas;
- geração sintética;
- variável alvo experimental;
- thresholds;
- estratégia de avaliação;
- limites éticos.

## Definição de uma boa mudança

Uma boa entrega:

- resolve um problema pedagógico/técnico concreto;
- mantém o estudante contextualizado, não reduzido a score;
- possui testes;
- preserva origem dos dados;
- mantém IA revisável;
- documenta limitações;
- evita refatoração não relacionada;
- deixa o projeto executável.

## Em caso de dúvida

Priorizar:

> **evidência → trajetória → acompanhamento humano**

em vez de:

> **score → ranking → decisão automática**.
