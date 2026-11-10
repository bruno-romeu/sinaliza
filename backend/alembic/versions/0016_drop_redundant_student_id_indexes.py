"""drop three student_id indexes already covered by a UNIQUE index

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-09

`ix_enrollments_student_id`, `ix_attendance_records_student_id` e
`ix_trajectory_changes_student_id` sao prefixos a esquerda de um indice UNIQUE
da mesma tabela que comeca exatamente por `student_id`:

    ix_enrollments_student_id         (student_id)
      <- uq_enrollment_student_classroom       (student_id, classroom_id)
    ix_attendance_records_student_id  (student_id)
      <- uq_attendance_student_classroom_date  (student_id, classroom_id, date)
    ix_trajectory_changes_student_id  (student_id)
      <- uq_trajectory_change_student_type_period
                                               (student_id, type, period_id)

Um B-tree atende qualquer predicado sobre um prefixo a esquerda de suas
colunas, entao o indice unico ja cobre toda busca por `student_id` nessas tres
tabelas. A condicao que torna isso valido e o unico **comecar** por
`student_id` — verificada no catalogo, e re-verificada por
`tests/test_redundant_indexes.py` a cada suite, para que a propriedade nao
dependa desta lista escrita a mao envelhecer junto com o schema.

O que esta remocao **nao** e: ganho de desempenho. Duas afirmacoes que
justificavam a remocao em `docs/deferred-work.md` foram medidas e nao se
sustentam como escritas.

- "o planner nunca os escolhe" e falso como afirmacao geral: um
  `WHERE student_id = ?` *sem* predicado de data em `attendance_records`
  escolhe sim `ix_attendance_records_student_id`, por ser menor (680 kB contra
  4416 kB do unico). O que e verdade e mais estreito — nenhuma consulta que a
  aplicacao emite tem essa forma; toda leitura por estudante tambem restringe
  `date`, e ai o indice unico atende o predicado composto inteiro. Verificado
  por `EXPLAIN (ANALYZE)` com os parametros reais de cada uma das instrucoes
  que as telas emitem, e por `EXPLAIN (GENERIC_PLAN)` para as formas
  parametrizadas.
- "escrita duplicada em todo INSERT" e real em principio mas nao mensuravel
  neste dataset: tres insercoes de 10.000 linhas em `attendance_records` com e
  sem os tres indices deram 459/241/187 ms contra 240/248/313 ms — faixas
  sobrepostas.

O que fica, entao, e higiene de schema: 728 kB no banco de demonstracao e um
indice a menos para manter, com cobertura provada e resultado de consulta
inalterado (78 resultados de caminho de leitura com o mesmo SHA-256 antes e
depois). Nenhuma coluna, constraint ou dado e tocado — so os tres indices —,
entao `downgrade()` os recria identicos e e simetrico de verdade.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (index name, table name) — a ordem de criacao no `downgrade` e a mesma do
# `upgrade`, so para que um diff de catalogo entre os dois sentidos nao dependa
# de ordem.
_REDUNDANT_INDEXES: tuple[tuple[str, str], ...] = (
    ("ix_enrollments_student_id", "enrollments"),
    ("ix_attendance_records_student_id", "attendance_records"),
    ("ix_trajectory_changes_student_id", "trajectory_changes"),
)


def upgrade() -> None:
    for index_name, table_name in _REDUNDANT_INDEXES:
        op.drop_index(index_name, table_name=table_name)


def downgrade() -> None:
    for index_name, table_name in _REDUNDANT_INDEXES:
        op.create_index(index_name, table_name, ["student_id"], unique=False)
