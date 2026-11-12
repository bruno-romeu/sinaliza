"""at most one open follow-up per (student, responsible user)

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-12

Fecha o D4 da passagem adversarial de QA (`docs/spec-qa-adversarial.md`,
Causa 3; `docs/spec-acompanhamento-aberto-unico-no-banco.md`).

`spec-ui-1` acrescentou o reaproveitamento de `POST /follow-ups` porque
acompanhamento aberto duplicado era defeito. A regra, porem, existia so como
`find_open_for_student` (SELECT) seguido de `save_with_evidence` (INSERT): duas
requisicoes que leem antes de qualquer uma escrever passam ambas pela
verificacao. Medido: a mesma trajetoria em duas abas, clique nas duas no mesmo
segundo, dois cards identicos na Home com a evidencia dividida entre eles.

O predicado
-----------
`UNIQUE (student_id, responsible_user_id) WHERE status <> 'ENCERRADO'`.

Tres escolhas, cada uma com motivo:

* **Parcial, nao total.** Um estudante pode legitimamente ter varios
  acompanhamentos ao longo do ano — abriu, conduziu, encerrou, meses depois
  abriu outro. O que nao pode e dois **simultaneos**. Os encerrados ficam fora
  do indice.
* **`<> 'ENCERRADO'` e nao uma lista dos tres abertos.** E literalmente o
  predicado que `find_open_for_student` ja usa. Escrever o complemento
  (`IN ('EM_OBSERVACAO', 'ACOMPANHAMENTO_ATIVO', 'AGUARDANDO_RETORNO')`)
  cobriria os mesmos valores hoje, mas um quinto estado acrescentado ao enum
  no futuro entraria em "aberto" para a aplicacao e ficaria de fora do indice —
  a restricao e a verificacao divergiriam em silencio. `ENCERRADO` e o unico
  estado que significa "o processo acabou"; `AGUARDANDO_RETORNO` continua
  sendo processo em curso.
* **`responsible_user_id` na chave.** O escopo por responsavel ja e o que toda
  leitura e escrita de `FollowUp` aplica (RF-22, `epic-4-retro-item-18`), e
  `find_open_for_student` reaproveita apenas dentro do mesmo responsavel. Uma
  unicidade so por `student_id` impediria duas coordenacoes de abrirem casos
  distintos para o mesmo estudante — regra que ninguem decidiu e que o teste
  `test_qa_opening_a_follow_up_never_reuses_another_users_case` recusa.

Nota: `ENCERRADO` **nao** e terminal no codigo — `ChangeFollowUpStatusService`
nao tem regra de adjacencia, qualquer estado e alvo valido a partir de qualquer
outro (AD-6). Logo, reabrir um encerrado quando ja existe outro aberto para o
mesmo par passa a ser recusado pelo banco. Isso e a mesma regra aplicada ao
mesmo caso, nao uma regra nova.

Dados ja existentes
-------------------
`upgrade()` procura duplicatas antes de criar o indice e **para** se achar
alguma, nomeando os pares. Nao apaga: `FollowUp` e processo humano com valor de
auditoria, e a migration 0014 tornou as duas FKs `RESTRICT` exatamente para que
um acompanhamento nao desapareca por efeito colateral. Escolher por conta
propria qual das duas linhas sobrevive seria apagar metade de um processo
humano numa migration — decisao que cabe a quem conduz o acompanhamento
(encerrar um dos dois), nao a este script.

Verificado no banco de demonstracao (`sinaliza-postgres-1`, base `sinaliza`): 5
linhas em `follow_ups`, nenhum par duplicado em aberto. A guarda e rede de
seguranca para outras instancias, nao mudanca de dado aqui.

`downgrade()` apenas derruba o indice — nenhuma coluna, constraint ou linha e
tocada, entao e simetrico de verdade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX_NAME = "uq_follow_up_open_per_student_and_owner"
_OPEN_PREDICATE = "status <> 'ENCERRADO'"


def upgrade() -> None:
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                f"""
                SELECT student_id, responsible_user_id, count(*) AS total
                FROM follow_ups
                WHERE {_OPEN_PREDICATE}
                GROUP BY student_id, responsible_user_id
                HAVING count(*) > 1
                ORDER BY student_id, responsible_user_id
                """
            )
        )
        .all()
    )
    if duplicates:
        listed = "; ".join(
            f"estudante {student_id} / responsavel {user_id}: {total} acompanhamentos abertos"
            for student_id, user_id, total in duplicates
        )
        raise RuntimeError(
            "A migration 0017 nao cria o indice unico parcial porque ja existem "
            "acompanhamentos abertos duplicados neste banco. Nenhuma linha foi "
            "alterada: um FollowUp e processo humano e a escolha de qual encerrar "
            "nao cabe a uma migration. Encerre um dos acompanhamentos de cada par "
            f"abaixo e rode novamente. {listed}"
        )

    op.create_index(
        _INDEX_NAME,
        "follow_ups",
        ["student_id", "responsible_user_id"],
        unique=True,
        postgresql_where=sa.text(_OPEN_PREDICATE),
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="follow_ups")
