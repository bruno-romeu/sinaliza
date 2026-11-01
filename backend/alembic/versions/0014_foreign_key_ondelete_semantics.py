"""explicit ondelete semantics on every foreign key

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-01

Fecha a lacuna catalogada em `deferred-work.md` desde a Story 1.5 e
reconfirmada na 3.2: nenhuma FK do schema declarava `ondelete`, de modo que
toda remoção de linha-pai caía no `NO ACTION` implícito do Postgres — um
comportamento por omissão, não uma decisão de domínio.

A semântica NÃO é a mesma para todas as tabelas:

* `CASCADE` onde a linha-filha **não tem significado próprio** sem o pai —
  fatos acadêmicos de um estudante (`attendance_records`, `grades`,
  `assignment_submissions`, `enrollments`, `pedagogical_observations`), a
  interpretação derivada desses fatos (`trajectory_changes` e suas
  `trajectory_change_sources`), as linhas de ligação de evidência
  (`follow_up_evidence` → `follow_ups`) e o dado experimental de ML
  (`ml_prediction` → `students`).

* `RESTRICT` onde apagar o pai **destruiria procedência ou um processo
  humano** e, portanto, precisa ser uma decisão explícita e não um efeito
  colateral:
  - `follow_ups.student_id` / `follow_ups.responsible_user_id` —
    `FollowUp` representa processo humano com valor de auditoria
    (`AGENTS.md` §Acompanhamento). Apagar um estudante não pode fazer o
    acompanhamento dele desaparecer silenciosamente: o processo tem de ser
    encerrado/resolvido antes.
  - `follow_up_action.*` — tabela append-only com `GRANT INSERT, SELECT` /
    `REVOKE UPDATE, DELETE` (AD-6). Um `CASCADE` seria executado pelo
    próprio sistema de integridade referencial, contornando esse `REVOKE` —
    exatamente o backstop que a migration 0009 instalou.
  - `follow_up_evidence.trajectory_change_id` — espelha no schema a regra de
    freeze-on-evidence que o repositório já aplica: uma `TrajectoryChange`
    citada como evidência não pode ser removida.
  - `pedagogical_observations.author_user_id` — a autoria é a origem do
    registro; `AGENTS.md` §NLP/LLM proíbe descartar a fonte.
  - `ml_prediction.model_version_id` — `AGENTS.md` §Versionamento de modelo:
    "Prediction deve apontar para a versão usada". Apagar a
    `MLModelVersion` que produziu um score tornaria o score não auditável.
  - `classroom_id` / `period_id` em toda parte — turma e período letivo são
    calendário compartilhado por muitos estudantes; removê-los não pode
    apagar os fatos de terceiros por tabela.

`trajectory_change_sources.source_id` continua **sem FK e sem `ondelete`, de
propósito**: a coluna é polimórfica (aponta para `AttendanceRecord`, `Grade`,
`AssignmentSubmission` ou `PedagogicalObservation` conforme `source_type`),
não existe FK possível e, portanto, nada para declarar aqui.

Observação honesta de escopo: no Postgres, `NO ACTION` (o que o schema tinha)
e `RESTRICT` só diferem quando a checagem é adiada (`DEFERRABLE`), o que não
ocorre aqui — para as FKs marcadas `RESTRICT` o comportamento em tempo de
execução é o mesmo de antes. O ganho é tornar a regra explícita e verificável
no catálogo, em vez de deixá-la implícita. Já as FKs marcadas `CASCADE` mudam
comportamento de fato.

Nenhuma migration anterior é editada (lição da epic 2): toda a mudança é feita
aqui, por `DROP CONSTRAINT` + `ADD CONSTRAINT`, e o `downgrade()` recria cada
FK exatamente na forma sem `ondelete` que existia em 0013.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (constraint_name, table, local_column, referred_table, ondelete)
FOREIGN_KEYS: tuple[tuple[str, str, str, str, str], ...] = (
    ("enrollments_student_id_fkey", "enrollments", "student_id", "students", "CASCADE"),
    ("enrollments_classroom_id_fkey", "enrollments", "classroom_id", "classrooms", "RESTRICT"),
    (
        "attendance_records_student_id_fkey",
        "attendance_records",
        "student_id",
        "students",
        "CASCADE",
    ),
    (
        "attendance_records_classroom_id_fkey",
        "attendance_records",
        "classroom_id",
        "classrooms",
        "RESTRICT",
    ),
    ("grades_student_id_fkey", "grades", "student_id", "students", "CASCADE"),
    ("grades_classroom_id_fkey", "grades", "classroom_id", "classrooms", "RESTRICT"),
    ("grades_period_id_fkey", "grades", "period_id", "academic_periods", "RESTRICT"),
    ("assignments_classroom_id_fkey", "assignments", "classroom_id", "classrooms", "RESTRICT"),
    ("assignments_period_id_fkey", "assignments", "period_id", "academic_periods", "RESTRICT"),
    (
        "assignment_submissions_assignment_id_fkey",
        "assignment_submissions",
        "assignment_id",
        "assignments",
        "CASCADE",
    ),
    (
        "assignment_submissions_student_id_fkey",
        "assignment_submissions",
        "student_id",
        "students",
        "CASCADE",
    ),
    (
        "pedagogical_observations_student_id_fkey",
        "pedagogical_observations",
        "student_id",
        "students",
        "CASCADE",
    ),
    (
        "pedagogical_observations_author_user_id_fkey",
        "pedagogical_observations",
        "author_user_id",
        "users",
        "RESTRICT",
    ),
    (
        "trajectory_changes_student_id_fkey",
        "trajectory_changes",
        "student_id",
        "students",
        "CASCADE",
    ),
    (
        "trajectory_changes_period_id_fkey",
        "trajectory_changes",
        "period_id",
        "academic_periods",
        "RESTRICT",
    ),
    (
        "trajectory_change_sources_trajectory_change_id_fkey",
        "trajectory_change_sources",
        "trajectory_change_id",
        "trajectory_changes",
        "CASCADE",
    ),
    ("follow_ups_student_id_fkey", "follow_ups", "student_id", "students", "RESTRICT"),
    (
        "follow_ups_responsible_user_id_fkey",
        "follow_ups",
        "responsible_user_id",
        "users",
        "RESTRICT",
    ),
    (
        "follow_up_evidence_follow_up_id_fkey",
        "follow_up_evidence",
        "follow_up_id",
        "follow_ups",
        "CASCADE",
    ),
    (
        "follow_up_evidence_trajectory_change_id_fkey",
        "follow_up_evidence",
        "trajectory_change_id",
        "trajectory_changes",
        "RESTRICT",
    ),
    (
        "follow_up_action_follow_up_id_fkey",
        "follow_up_action",
        "follow_up_id",
        "follow_ups",
        "RESTRICT",
    ),
    (
        "follow_up_action_author_user_id_fkey",
        "follow_up_action",
        "author_user_id",
        "users",
        "RESTRICT",
    ),
    ("ml_prediction_student_id_fkey", "ml_prediction", "student_id", "students", "CASCADE"),
    (
        "ml_prediction_model_version_id_fkey",
        "ml_prediction",
        "model_version_id",
        "ml_model_version",
        "RESTRICT",
    ),
)


def upgrade() -> None:
    for name, table, column, referred_table, ondelete in FOREIGN_KEYS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name,
            table,
            referred_table,
            [column],
            ["id"],
            ondelete=ondelete,
        )


def downgrade() -> None:
    for name, table, column, referred_table, _ondelete in FOREIGN_KEYS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(name, table, referred_table, [column], ["id"])
