"""QA adversarial — entradas hostis na fronteira HTTP.

Escrito por quem nao implementou nenhuma destas rotas. O que estes testes
procuram nao e cobertura: e a diferenca entre **422 limpo** e **500 feio** na
borda de cada entrada que o cliente controla.

Dois defeitos confirmados (`docs/spec-qa-adversarial.md`, D1 e D2), ambos com a
mesma causa: `app/presentation/errors.py` registra handler para `AppError`,
`IntegrityViolationError` e `RepositoryIntegrityError`, e **nenhum** para
`sqlalchemy.exc.DataError` — a familia "o valor nao e representavel no tipo da
coluna". Os dois testes `xfail` abaixo mostram os dois gatilhos alcancaveis.

Nota sobre o que os `xfail` afirmam: o `TestClient` do Starlette repropaga a
excecao do servidor em vez de devolver 500 (`raise_server_exceptions=True`,
o padrao, que o resto da suite tambem usa). Sob `uvicorn` isto e um HTTP 500.
Os testes afirmam o 422 que deveria acontecer; hoje a chamada levanta
`DataError` antes de qualquer `assert`, o que e exatamente o que torna o
`xfail(strict=True)` honesto.

O resto do arquivo sao os resultados **negativos**: fronteiras que ja
respondem corretamente e que esta passagem fixa como invariante, para que a
proxima mudanca nao possa afrouxa-las em silencio.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.db.models import ClassroomModel, StudentModel, UserModel

_ZERO_UUID = "00000000-0000-0000-0000-000000000000"


def _auth_headers(client: TestClient, user: UserModel) -> dict[str, str]:
    """Um unico login por teste — `POST /auth/login` tem limite de 10
    tentativas por 300s (`app/presentation/rate_limit.py`)."""
    response = client.post(
        "/auth/login", json={"email": user.email, "password": "Senha-Correta-123"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# ---------------------------------------------------------------------------
# D1 — `page` sem limite superior derruba a rota com `bigint out of range`
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "D1: `GET /home` e `GET /home/search` limitam `page_size` com "
        "`ge=1, le=MAX_*` mas limitam `page`/`changes_page`/`follow_ups_page` "
        "so com `ge=1`. `offset = (page - 1) * page_size` estoura o `bigint` "
        "do Postgres e o `sqlalchemy.exc.DataError` resultante nao tem "
        "handler em `app/presentation/errors.py`, virando 500 sob uvicorn. "
        "Fecha com um `le=` em cada um dos tres `Query(...)`, espelhando o "
        "que o `page_size` irmao ja faz na mesma assinatura."
    ),
)
@pytest.mark.parametrize(
    "url",
    [
        "/home/search?q=a&page=9223372036854775807",
        "/home/search?q=a&page=99999999999999999999",
        "/home?changes_page=99999999999999999999",
        "/home?follow_ups_page=99999999999999999999",
    ],
)
def test_qa_oversized_page_answers_422_instead_of_crashing(
    client: TestClient, seeded_user: UserModel, url: str
) -> None:
    response = client.get(url, headers=_auth_headers(client, seeded_user))
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# D2 — byte NUL em texto livre derruba o INSERT
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "D2: `\\u0000` atravessa `StringConstraints(strip_whitespace=True, "
        "min_length=1)` intacto e o psycopg recusa o INSERT com "
        "`PostgreSQL text fields cannot contain NUL (0x00) bytes`. O "
        "`sqlalchemy.exc.DataError` resultante nao tem handler, entao vira "
        "500 em vez do 422 que qualquer outro texto invalido recebe. Mesma "
        "causa de D1."
    ),
)
def test_qa_nul_byte_in_observation_text_answers_422_instead_of_crashing(
    client: TestClient,
    seeded_user: UserModel,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    response = client.post(
        "/pedagogical-observations",
        headers=_auth_headers(client, seeded_user),
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(seeded_classroom.id),
            "text": "registro\u0000truncado",
        },
    )
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# D5 — data sem faixa: aceita, confirmada, e invisivel para sempre
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "D5: `AttendanceCreateRequest.date` nao tem faixa e o "
        '`<input type="date">` do `Presenca.tsx` nao tem `min`/`max`. Um '
        "erro de digitacao no ano grava o fato, devolve 201 e a tela diz "
        "'Registro salvo.' — mas toda leitura de trajetoria e truncada em "
        "`as_of()` e nao existe endpoint de releitura de presenca, entao o "
        "registro nunca mais aparece em lugar nenhum, nem para ser "
        "corrigido. Fecha com uma faixa de data plausivel no schema."
    ),
)
@pytest.mark.parametrize("impossible_date", ["2999-12-31", "0001-01-01"])
def test_qa_attendance_outside_any_plausible_school_year_is_refused(
    client: TestClient,
    seeded_user: UserModel,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    impossible_date: str,
) -> None:
    response = client.post(
        "/attendance",
        headers=_auth_headers(client, seeded_user),
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(seeded_classroom.id),
            "date": impossible_date,
            "status": "PRESENT",
        },
    )
    assert response.status_code == 422, response.text


@pytest.mark.xfail(
    strict=True,
    reason=(
        "D5 (segunda metade): o Pydantic coage um **inteiro** a data tratando-o "
        "como tempo Unix, entao `{'date': 0}` vira `1970-01-01` com 201. Um "
        "cliente que mande o tipo errado nao e avisado — recebe confirmacao e "
        "um fato escolar errado. Fecha com `strict`/validator no campo."
    ),
)
def test_qa_integer_date_is_refused_instead_of_becoming_1970(
    client: TestClient,
    seeded_user: UserModel,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    response = client.post(
        "/attendance",
        headers=_auth_headers(client, seeded_user),
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(seeded_classroom.id),
            "date": 0,
            "status": "PRESENT",
        },
    )
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Resultados negativos — fronteiras que ja respondem certo, fixadas aqui
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # `window_days` tem `gt=0, le=3650`: as duas pontas fecham.
        (f"/students/{_ZERO_UUID}/trajectory?window_days=0", 422),
        (f"/students/{_ZERO_UUID}/trajectory?window_days=-5", 422),
        (f"/students/{_ZERO_UUID}/trajectory?window_days=99999999999999999999", 422),
        # UUID malformado morre na validacao, nunca no servico.
        ("/students/not-a-uuid/trajectory", 422),
        # `page`/`page_size` na ponta de baixo sao cobertos por `ge=1`.
        ("/home/search?q=a&page=0", 422),
        ("/home/search?q=a&page=-1", 422),
        ("/home/search?q=a&page_size=0", 422),
        ("/home/search?q=a&page_size=101", 422),
        # Id valido e inexistente e 404 no envelope do projeto, nunca 500.
        (f"/students/{_ZERO_UUID}/trajectory", 404),
        (f"/follow-ups/{_ZERO_UUID}", 404),
    ],
)
def test_qa_query_and_path_boundaries_answer_cleanly(
    client: TestClient, seeded_user: UserModel, url: str, expected: int
) -> None:
    response = client.get(url, headers=_auth_headers(client, seeded_user))
    assert response.status_code == expected, response.text


@pytest.mark.parametrize(
    "value",
    [
        "NaN",
        "sNaN",
        "Infinity",
        "-Infinity",
        10.001,  # mais casas do que `Numeric(4,2)` aceita
        "1E-10",
        10.01,
        -0.01,
    ],
)
def test_qa_non_representable_grade_values_answer_422(
    client: TestClient,
    seeded_user: UserModel,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period,
    value: object,
) -> None:
    """A dupla validacao de `GradeCreateRequest.value` (`ge=0, le=10,
    max_digits=4, decimal_places=2`) segura todo valor nao representavel antes
    do `CHECK` do banco — inclusive `NaN`/`Infinity`, que uma comparacao
    ingenua com `ge`/`le` deixaria passar."""
    response = client.post(
        "/grades",
        headers=_auth_headers(client, seeded_user),
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(seeded_classroom.id),
            "subject": "Matemática",
            "period_id": str(seeded_academic_period.id),
            "date": "2026-09-01",
            "value": value,
        },
    )
    assert response.status_code == 422, response.text


def test_qa_impossible_calendar_date_answers_422(
    client: TestClient,
    seeded_user: UserModel,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    """30 de fevereiro nao existe — e recusado pelo parser de data, nao pelo
    banco."""
    response = client.post(
        "/attendance",
        headers=_auth_headers(client, seeded_user),
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(seeded_classroom.id),
            "date": "2026-02-30",
            "status": "PRESENT",
        },
    )
    assert response.status_code == 422, response.text


def test_qa_search_treats_like_wildcards_as_literal_text(
    client: TestClient,
    seeded_user: UserModel,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    """`%` e `_` sao curingas de `LIKE`. Sem `escape=`, `?q=%` devolveria a
    turma inteira e `?q=_` casaria qualquer estudante de nome com uma letra —
    uma listagem de estudantes que ninguem pediu, da fronteira de busca.
    `SqlAlchemyStudentRepository` passa `escape="\\\\"`, entao os dois sao
    texto literal e nao casam nada."""
    headers = _auth_headers(client, seeded_user)
    for wildcard in ("%", "_", "%%"):
        response = client.get(f"/home/search?q={wildcard}", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["results"] == [], wildcard


def test_qa_unicode_and_bidi_text_round_trips_intact(
    client: TestClient,
    seeded_user: UserModel,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    """Emoji fora do BMP e marca de sobreposicao direita-para-esquerda sao
    gravados e devolvidos sem perda: a coluna e `Text`, nao `latin-1`, e nada
    no caminho reescreve o texto da observacao."""
    text = "Participou menos \U0001f600 ‮RTL‬ ção"
    response = client.post(
        "/pedagogical-observations",
        headers=_auth_headers(client, seeded_user),
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(seeded_classroom.id),
            "text": text,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["text"] == text
