# Modelo de Dados — MVP

Este documento registra o modelo de dados mínimo para a primeira fatia vertical do projeto, cobrindo as Etapas 1–3 do roadmap (Domínio e Dados, Trajetória, Acompanhamento). Entidades de NLP derivado (`ExtractedSignal`, `SignalReview`) e de ML (`MLModelVersion`, `MLPrediction`) ficam fora deste rascunho — entram nas Etapas 4 e 5, quando forem desenhadas. `PedagogicalObservation` (o registro pedagógico bruto, RF-08/RF-09) **está** neste rascunho — é fato observável de MVP (Etapa 3), não uma entidade derivada de NLP; a agregação anterior dos dois na mesma linha "Etapa 5" era um erro de rascunho, corrigido abaixo.

Este modelo cobre dados sintéticos, conforme definido no README e no AGENTS.md.

> Atualizado por `docs/architecture/architecture-sinaliza-2026-09-17/ARCHITECTURE-SPINE.md` (AD-1, AD-4, AD-7, AD-10, AD-11): `role` de `User` reduzido a valor único (perfil único, PRD RF-02), `AttendanceRecord.present` virou `status` + `UNIQUE(student_id, classroom_id, date)` (resolve `[NOTE FOR PM]` do RF-03 e RF-04/RNF-11), `Grade.value` fixado em escala 0–10 (resolve `[NOTE FOR PM]` do RF-05), `source_record_ids[]` de `TrajectoryChange` formalizado como tabela de junção, `TrajectoryChange` ganha `period_id` (chave de upsert de AD-1), `PedagogicalObservation` definida (antes ausente e incorretamente listada como Etapa 5), e `Student` ganha `dataset_split` (RF-23).

---

## Domínio

```
User            { id, name, email, role: COORDENACAO_PEDAGOGICA }
Classroom       { id, name, academic_year }
AcademicPeriod  { id, label, start_date, end_date, order_index }
Student         { id, name, dataset_split: TRAIN | EVAL_DEMO, synthetic_profile: SyntheticProfile | null }
Enrollment      { id, student_id, classroom_id }
```

`role` tem um único valor possível hoje (perfil único, RF-02) — mantido como enum só por extensibilidade estrutural futura, nunca um segundo valor "professor" (proibido em nomenclatura de produto/código, ver PRD §2.1 e addendum do brief).

`dataset_split` decide, na geração sintética (nunca em query time), se o estudante pertence ao recorte de treino ou de avaliação/operação/demo (RF-23) — nunca três bases separadas.

`synthetic_profile` é nullable: um estudante criado pelo fixture de desenvolvimento não tem perfil, e um estudante gerado pelo gerador sintético (Epic 2) sempre tem. Ver "Geração sintética" abaixo.

`AcademicPeriod` representa o período letivo oficial (ex: bimestre/trimestre). É o contexto usado por `Grade` e por matrícula — não é a granularidade usada para calcular trajetória (ver seção seguinte).

## Fatos observáveis

```
AttendanceRecord     { id, student_id, classroom_id, date, status: PRESENT | ABSENT_JUSTIFIED | ABSENT_UNJUSTIFIED }  -- UNIQUE(student_id, classroom_id, date)
Grade                { id, student_id, classroom_id, subject, period_id, date, value: numeric(4,2) }
Assignment           { id, classroom_id, subject, period_id, due_date }
AssignmentSubmission { id, assignment_id, student_id, status: DELIVERED | NOT_DELIVERED | PARTIAL, date }
PedagogicalObservation { id, student_id, author_user_id, text, created_at }
```

Estes são fatos registrados pela coordenação pedagógica na rotina (chamada, avaliação, entrega, observação). Não existe entidade `Assessment` separada — `subject`/`date` ficam direto em `Grade` para reduzir indireção sem perda de informação relevante ao MVP.

`AttendanceRecord.status` distingue falta justificada de não justificada (resolve o `[NOTE FOR PM]` do RF-03); RF-11 conta as duas igualmente no cálculo de tendência no MVP, por simplicidade — o campo fica gravado para uso futuro. A constraint `UNIQUE(student_id, classroom_id, date)` impede duplicidade de registro em nível de banco (RF-04, RNF-11) — não apenas checagem de aplicação. `Grade.value` é fixado em escala 0.0–10.0 (resolve o `[NOTE FOR PM]` do RF-05); nenhum RF exige semântica de aprovação/reprovação, então não há campo derivado para isso.

`PedagogicalObservation` é o registro em texto livre (RF-08); não tem `follow_up_id` — é sobre o estudante, não sobre um acompanhamento específico (RF-08 diz "sobre um estudante"; RF-09 só exige referência ao registro original em qualquer sinal derivado). Antes de ser citado como fonte de uma `TrajectoryChange` evidenciada por um `FollowUp`, é visível a qualquer usuário autenticado (perfil único); depois disso, sua exibição fica escopada pela regra de AD-8 (arquitetura) — nunca um filtro na própria tabela.

## Geração sintética

```
SyntheticGenerationRun { id, seed, generator_version, executed_at, student_count, train_ratio }
SyntheticProfile       -- enum: STABLE | FALLING_ATTENDANCE | COMBINED_DETERIORATION | ...
```

`SyntheticGenerationRun` é a única entidade nova da Epic 2. Registra a proveniência de cada execução do gerador — a seed usada, a versão do gerador e a data de execução — para que qualquer base sintética possa ser reproduzida ou auditada depois (RNF-13, AC de Story 2.1). `train_ratio` fica persistido junto porque a proporção entre os dois recortes é uma decisão de geração, não uma constante global: uma base gerada com uma proporção diferente precisa ser identificável como tal.

`SyntheticProfile` não é uma tabela — é um enum persistido em `Student.synthetic_profile`. Cada valor corresponde a uma regra determinística e documentada de evolução de frequência/notas/atividades ao longo do ano letivo (Story 2.2), nunca geração aleatória opaca. O conjunto inclui obrigatoriamente ao menos um perfil estável (sem mudança) e um de deterioração combinada (frequência + nota + atividades juntos), que é o espectro que a regra de convergência do RF-11 precisa conseguir distinguir.

**O perfil vive em `Student`, não numa tabela de rótulos à parte**, porque a Epic 5 precisa validar a detecção de mudança estudante a estudante contra o desfecho conhecido — um JOIN a mais em toda validação não paga o isolamento que ele compraria. Em troca, vale a mesma regra do score de ML (AD-3): `synthetic_profile` **nunca** aparece em endpoint ou schema de resposta do produto (`/students/*`, `/follow-ups/*`, páginas de lançamento). É rótulo de pesquisa, não dado de produto — expô-lo na aplicação web transformaria a demonstração numa profecia auto-realizável, além de vazar o gabarito da avaliação.

Nenhuma tabela paralela existe para dado sintético: presença, notas, atividades e observações geradas são linhas das mesmas tabelas de "Fatos observáveis" acima, sujeitas às mesmas constraints de integridade (`UNIQUE(student_id, classroom_id, date)`, `CHECK` de 0–10 em `Grade.value`). O gerador nunca produz dado que a aplicação não produziria.

## Trajetória

```
TrajectorySnapshot {
  id, student_id, snapshot_date, window_days,
  attendance_rate, attendance_trend,
  grade_average, grade_trend,
  missing_assignments_count, missing_assignment_delta
}

TrajectoryChange {
  id, student_id, type, period_id, detected_at, description
}  -- UNIQUE(student_id, type, period_id)

TrajectoryChangeSource {
  id, trajectory_change_id, source_type: ATTENDANCE_RECORD | GRADE | ASSIGNMENT_SUBMISSION | PEDAGOGICAL_OBSERVATION, source_id
}
```

`period_id` referencia o `AcademicPeriod`/bimestre em que a convergência foi detectada — é a chave de upsert que dá estabilidade a `FollowUpEvidence.trajectory_change_id` (arquitetura, AD-1): uma vez que uma `TrajectoryChange` tem `FollowUpEvidence` apontando para ela, recomputações futuras não a alteram mais (congelada); antes disso, é livremente substituída (`description`/`detected_at`/suas `TrajectoryChangeSource`) a cada recomputação.

**"Fator Preocupante" não tem tabela.** É um sinal isolado que ainda não convergiu com outro no mesmo `period_id` (RF-11) — nunca persistido, computado e devolvido só dentro da resposta HTTP que o exibe, sem id estável, nunca citável por `FollowUpEvidence`. Se convergir numa requisição futura, vira uma `TrajectoryChange` real pela regra acima.

`TrajectorySnapshot` é recalculado em **janela rolante** (`window_days`, ex: 30 dias / 8 semanas), não amarrado a `AcademicPeriod`. Frequência e atividades entregues são sinais contínuos e "faltas consecutivas"/"últimas 8 semanas" não cabem numa granularidade de bimestre — enquanto nota continua reportada por período oficial via `Grade.period_id`.

`type` é um enum fechado (rascunho inicial, sujeito a revisão ao implementar a regra de detecção):

```
ATTENDANCE_DROP
GRADE_DROP
MISSING_ASSIGNMENTS_INCREASE
COMBINED_DETERIORATION
```

`TrajectoryChangeSource` referencia os registros de origem (`AttendanceRecord`, `Grade`, `AssignmentSubmission` ou `PedagogicalObservation`) que sustentam a mudança — toda mudança exibida deve apontar para dado-fonte, nunca "IA identificou risco". É FK real (não array solto), inserida na mesma transação que a `TrajectoryChange` (RNF-11) — nenhuma `TrajectoryChange` existe sem ao menos uma linha aqui.

## Acompanhamento

```
FollowUp         { id, student_id, status, reason, responsible_user_id, next_review_date, created_at }
FollowUpEvidence { id, follow_up_id, trajectory_change_id }
FollowUpAction   { id, follow_up_id, description, author_user_id, created_at }
```

`status` segue os estados definidos no README/AGENTS.md:

```
EM_OBSERVACAO
ACOMPANHAMENTO_ATIVO
AGUARDANDO_RETORNO
ENCERRADO
```

Não existe estado `HIGH_RISK` nem substituto — acompanhamento é processo humano, não classificação automática.

---

## Decisões registradas

- **Escopo:** frequência, notas e atividades entram juntas na primeira fatia (não só frequência), para permitir perfis sintéticos combinados (ex: deterioração combinada) desde o início.
- **Granularidade de trajetória:** dissociada de `AcademicPeriod`. `TrajectorySnapshot`/`TrajectoryChange` usam janela rolante; `AcademicPeriod` fica restrito ao contexto de nota/matrícula.
- **Sem `Assessment`:** simplificado — `subject`/`date` diretamente em `Grade`.
- **Perfil único (`User.role`):** valor único `COORDENACAO_PEDAGOGICA`; nunca um segundo valor "professor" (arquitetura, AD-8).
- **Falta com justificativa e escala de nota:** `AttendanceRecord.status` e `Grade.value` fixados (arquitetura, AD-10) — resolvem os dois `[NOTE FOR PM]` do PRD.
- **Evidência como FK real:** `TrajectoryChangeSource` substitui `source_record_ids[]` (arquitetura, AD-7) — integridade garantida por FK + transação de escrita única, não só checagem de aplicação solta.
- **`TrajectorySnapshot`/`TrajectoryChange` calculados sob demanda:** nunca por job agendado; upsert síncrono (chave `student_id + type + period_id`, congelado uma vez evidenciado) dentro da própria requisição que os lê (arquitetura, AD-1).
- **Split de dataset:** `Student.dataset_split` (arquitetura, AD-4) — decidido na geração sintética, nunca em query time.
- **`PedagogicalObservation` trazida para o MVP:** definida acima (arquitetura, AD-8/AD-11) — corrige a agregação anterior com entidades de NLP (Etapa 5), que era um erro de escopo deste rascunho.
- **Duplicidade de presença em nível de banco:** `UNIQUE(student_id, classroom_id, date)` em `AttendanceRecord` (arquitetura, AD-7) — resolve RF-04/RNF-11.
- **Proveniência de geração persistida:** `SyntheticGenerationRun` (seed + versão do gerador + data) — sem ela o determinismo do gerador é inverificável depois do fato (RNF-13, Epic 2).
- **Perfil sintético em `Student`, fora da API do produto:** `Student.synthetic_profile` nullable, consultável pela avaliação offline e nunca exposto em schema de resposta do produto — mesma fronteira que AD-3 impõe ao score de ML.
- **"Fator Preocupante" nunca persistido:** puramente computado por requisição (arquitetura, AD-1) — nenhuma tabela nova para ele.

## Fora deste rascunho (etapas futuras)

```
ExtractedSignal, SignalReview   -- Etapa 5 (NLP, derivado de PedagogicalObservation)
MLModelVersion, MLPrediction     -- Etapa 4 (ML)
```
