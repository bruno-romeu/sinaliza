"""A faixa aceita para a data de um fato escolar, compartilhada pelos
schemas de presença, nota e atividade.

Sem faixa, `2999-12-31` e `0001-01-01` eram gravados com 201, e o Pydantic
ainda coagia **inteiro** a data (`{"date": 0}` virava `1970-01-01`, tempo
Unix), devolvendo confirmação a um cliente que mandou o tipo errado — ver
`_reject_numeric` para por que a correção disso não é `Field(strict=True)`. O que
torna isso pior que um dado feio no banco: toda leitura de trajetória é
truncada em `as_of()` (`filter_as_of`, aplicado às quatro colunas de data de
fato) e não existe endpoint de releitura de presença/nota/entrega — então um
ano digitado errado é confirmado com "Registro salvo." e nunca mais aparece,
nem para ser corrigido (D5 de `docs/spec-qa-adversarial.md`).

**De onde vem o teto.** Não é número escolhido a dedo: é a própria regra de
leitura do projeto. `filter_as_of` trunca em `as_of()`, logo um fato datado
depois de `as_of()` é algo que o sistema, pela sua própria regra, nunca vai
ler. A guarda diz literalmente "não gravamos o que não conseguiríamos ler", e
acompanha de graça o `SINALIZA_DEMO_AS_OF` do ensaio.

`due_date` é a exceção justificada: cadastrar a atividade antes do prazo é o
fluxo natural do professor, e a truncagem faz a atividade aparecer quando a
data chega — comportamento pretendido, não defeito. Seu teto é um ano à
frente, o horizonte do MVP (`AGENTS.md`: "um ano letivo").

**De onde vem o piso.** Cinco anos atrás é folgado em relação ao mesmo
horizonte de um ano letivo, e recusa tanto `0001-01-01` quanto o
`1970-01-01` que a coerção de inteiro produzia.

**Por que não derivar de `academic_periods`.** Investigado e descartado
(`docs/spec-correcao-defeitos-qa.md`): `AttendanceRecordModel` não tem
`period_id`, então para presença seria preciso consultar o banco dentro do
caminho de validação de um POST — contra `AGENTS.md` §API; e os períodos são
fixture de desenvolvimento, cujas janelas semeadas não cobrem nem a data de
hoje, o que transformaria uma guarda de digitação num portão de calendário
que os dados do MVP não honram.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator

from app.domain.as_of import as_of

#: Quantos anos para trás uma data de fato pode estar.
PAST_YEARS = 5

#: Quantos dias à frente de `as_of()` um **prazo** pode estar. Um ano; a
#: data de um fato *ocorrido* não pode estar à frente nenhum dia.
FUTURE_DAYS_FOR_DUE_DATE = 365

_DAYS_PER_YEAR = 365


def earliest_accepted_date() -> date:
    """O piso, recalculado a cada validação — `as_of()` é lido fresco do
    ambiente a cada chamada por desenho (ver `app/domain/as_of.py`), e um
    limite congelado na importação deixaria de acompanhá-lo."""
    return as_of() - timedelta(days=PAST_YEARS * _DAYS_PER_YEAR)


def _reject_numeric(value: object) -> object:
    """Recusa número onde se espera data.

    O Pydantic, no modo permissivo, lê um inteiro como tempo Unix: `0` virava
    `1970-01-01` e o cliente recebia 201 por um fato escolar que ninguém
    mandou. `Field(strict=True)` fecharia isso em JSON puro, mas **não serve
    aqui**: o FastAPI desserializa o corpo e valida o `dict` resultante em
    modo Python, onde `strict` recusa também a string ISO-8601 que todo
    cliente legítimo manda. Recusar explicitamente o numérico é a guarda que
    fecha o buraco sem fechar a porta."""
    if isinstance(value, bool | int | float):
        raise ValueError("A data precisa ser uma string no formato AAAA-MM-DD.")
    return value


def _validate_occurred(value: date) -> date:
    floor, ceiling = earliest_accepted_date(), as_of()
    if not floor <= value <= ceiling:
        raise ValueError(
            f"A data precisa estar entre {floor.isoformat()} e {ceiling.isoformat()} — "
            "um fato escolar não acontece em dia que ainda não chegou, e um registro "
            "fora dessa faixa não apareceria em nenhuma leitura."
        )
    return value


def _validate_due(value: date) -> date:
    floor = earliest_accepted_date()
    ceiling = as_of() + timedelta(days=FUTURE_DAYS_FOR_DUE_DATE)
    if not floor <= value <= ceiling:
        raise ValueError(
            f"O prazo precisa estar entre {floor.isoformat()} e {ceiling.isoformat()}."
        )
    return value


#: A data em que um fato escolar **aconteceu**: presença, nota, entrega.
SchoolFactDate = Annotated[
    date, BeforeValidator(_reject_numeric), AfterValidator(_validate_occurred)
]

#: O prazo de entrega de uma atividade — a única data que pode estar à frente
#: de `as_of()`.
AssignmentDueDate = Annotated[date, BeforeValidator(_reject_numeric), AfterValidator(_validate_due)]
