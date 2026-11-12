# 0005 — A faixa aceita para a data de um fato escolar é ancorada em `as_of()`

- **Data:** 2026-11-12
- **Status:** aceita
- **Fecha:** `docs/spec-qa-adversarial.md` §Open questions ("D5 se corrige com
  faixa de data no schema (qual faixa?)")
- **Spec:** `docs/spec-correcao-defeitos-qa.md`

## Contexto

`AttendanceCreateRequest.date`, `GradeCreateRequest.date`,
`AssignmentSubmissionCreateRequest.date` e `AssignmentCreateRequest.due_date`
não tinham limite nenhum: `2999-12-31` e `0001-01-01` eram gravados com 201, e
o Pydantic ainda coagia inteiro a data (`{"date": 0}` virava `1970-01-01`).

O que torna isso pior que um dado feio no banco é a combinação com duas outras
propriedades do sistema: toda leitura de trajetória é truncada em `as_of()`
(`filter_as_of`, aplicado às quatro colunas de data de fato) e **não existe
endpoint de releitura** de presença, nota ou entrega. A coordenação digita
2027 em vez de 2026, a tela diz "Registro salvo.", e o registro nunca mais
aparece — nem para ser corrigido.

## Decisão

**A faixa é derivada de `as_of()`, não de uma constante nem dos
`academic_periods`.** Declarada em
`backend/app/presentation/schemas/school_dates.py`:

| data | piso | teto |
| --- | --- | --- |
| fato ocorrido (presença, nota, entrega) | `as_of()` − 5 anos | `as_of()` |
| prazo de atividade (`due_date`) | `as_of()` − 5 anos | `as_of()` + 365 dias |

Mais um `BeforeValidator` que recusa valor numérico, fechando a coerção de
inteiro a tempo Unix. `Field(strict=True)` foi tentado primeiro e não serve:
o FastAPI desserializa o corpo e valida o `dict` em modo **Python**, onde
`strict` recusa também a string ISO-8601 de qualquer cliente legítimo — 22
testes existentes quebraram ao medir isso.

O teto do fato ocorrido não é número escolhido a dedo: é a própria regra de
leitura do projeto. Se `filter_as_of` trunca em `as_of()`, um fato datado
depois disso é algo que o sistema, pela sua própria regra, nunca vai ler — a
guarda diz literalmente "não gravamos o que não conseguiríamos ler", e
acompanha o `SINALIZA_DEMO_AS_OF` do ensaio de graça. `due_date` é a exceção
justificada: cadastrar a atividade antes do prazo é o fluxo natural do
professor, e a truncagem faz a atividade aparecer quando a data chega — isso é
comportamento pretendido. O piso de cinco anos é folgado em relação ao
horizonte do MVP ("um ano letivo") e recusa tanto `0001-01-01` quanto o
`1970-01-01` da coerção de inteiro.

## Alternativas descartadas

**Faixa fixa em constante** (ex. `2000-01-01 .. 2100-12-31`): não fecha a
mordida. O caso real é digitar 2027 em vez de 2026, e uma constante larga
aceita 2027 exatamente como antes.

**Faixa derivada de `academic_periods`.** Investigada e descartada por três
motivos: (1) `AttendanceRecordModel` não tem `period_id` — só `Grade` e
`Assignment` têm —, então para presença seria preciso perguntar ao banco
"algum período contém esta data?" dentro do caminho de validação de um POST,
contra `AGENTS.md` §API (controllers finos, nada de regra de serviço na
borda); (2) os períodos são fixture de desenvolvimento e as janelas semeadas
não cobrem nem a data de hoje, o que transformaria uma guarda de digitação num
portão de calendário que os dados do MVP não honram; (3) grade e atividade
ficariam com regra mais estrita que presença sem que o usuário conseguisse
prever a diferença.

**Endpoint de releitura/correção.** É a resposta certa para a outra metade do
defeito ("nem para ser corrigido"), já adiada em `docs/deferred-work.md` desde
a Story 1.3. É RF nova — rota, serviço e tela —, não correção de defeito.

## Consequências

- O frontend declara `min`/`max` nos quatro `<input type="date">` das telas de
  lançamento (`frontend/src/pages/Lancamento/dateBounds.ts`), espelhando a
  mesma faixa com o "hoje" do navegador. O backend continua sendo a
  autoridade.
- Sob um `SINALIZA_DEMO_AS_OF` recuado, lançar um fato com a data real de hoje
  passa a ser recusado. É consistente: aquele registro seria invisível sob o
  mesmo pino.
- O piso de cinco anos é o número a rever se o projeto algum dia importar
  histórico antigo.
