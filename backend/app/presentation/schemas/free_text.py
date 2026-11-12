"""O tipo de texto livre que os schemas de entrada compartilham.

Um `Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]`
sozinho não cobre tudo o que a coluna recusa: o byte NUL (`\\u0000`)
atravessa `strip_whitespace` e `min_length` intacto e só é recusado lá no
fundo, pelo psycopg — `PostgreSQL text fields cannot contain NUL (0x00)
bytes` —, o que fazia um texto inválido virar 500 em vez do 422 que todo
outro texto inválido recebe (D2 de `docs/spec-qa-adversarial.md`).

A recusa é **só** do NUL, e não de caracteres de controle em geral: o resto
do Unicode atravessa a coluna `Text` sem perda, e um teste existente fixa
isso para emoji fora do BMP e para marcas de direção bidirecional. Alargar a
regra aqui recusaria texto que o banco aceita de bom grado.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, StringConstraints

_NUL = "\x00"


def _reject_nul_bytes(value: str) -> str:
    if _NUL in value:
        raise ValueError("O texto não pode conter o caractere nulo (U+0000).")
    return value


#: Texto livre sem limite de tamanho — observação pedagógica, descrição de
#: ação de acompanhamento. Mapeia para uma coluna `Text`.
FreeText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    AfterValidator(_reject_nul_bytes),
]

#: Texto curto de uma linha — a disciplina de nota e de atividade. O
#: `max_length` espelha o `String(255)` da coluna.
ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    AfterValidator(_reject_nul_bytes),
]
