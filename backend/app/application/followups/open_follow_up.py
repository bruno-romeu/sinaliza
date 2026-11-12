"""`OpenFollowUpService` — the application-layer entry point for
`POST /follow-ups` (Story 4.1, RF-12).

Opening a follow-up is always an explicit click: a new `TrajectoryChange`
is never auto-attached to an already-open `FollowUp` (AD-1, spec Boundaries
& Constraints). What the click does depends on what already exists
(spec-ui-1 "Acompanhamento duplicado"):

- no open (non-`ENCERRADO`) `FollowUp` for this student and responsible
  user: a brand new `FollowUp` is created, exactly as before (`created=True`);
- an open one already exists: it is reused (`created=False`). If the clicked
  change is not linked to it yet, one `FollowUpEvidence` row is added, so the
  explicit click still records the new evidence instead of silently
  dropping it; clicking again on an already-linked change writes nothing.

Before this, every click created another `FollowUp`, so a double click or a
second visit to the trajectory page left duplicate open cases.

Esse `SELECT`-depois-`INSERT` e uma verificacao, nao uma garantia: duas
requisicoes que leiam antes de qualquer uma escrever passam ambas por ele (D4,
`docs/spec-acompanhamento-aberto-unico-no-banco.md`). Quem garante e o indice
unico parcial `uq_follow_up_open_per_student_and_owner` (migration 0017), e
este servico trata a recusa dele como o que ela significa: outra requisicao
acabou de abrir o acompanhamento deste estudante. Perder a corrida cai no
**mesmo** caminho de reaproveitamento (`created=False`, HTTP 200) em vez de
virar erro de tela — a intencao de `spec-ui-1` e justamente que o segundo
clique receba o caso que ja existe.

`status` is always `EM_OBSERVACAO`; `reason`/`next_review_date` are always
`None` — no UI captures them in this story (spec Design Notes).
`responsible_user_id` is always the caller-supplied authenticated user, never
a request field (spec Boundaries & Constraints) — the router is responsible
for sourcing it from `get_current_user`, never this service.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.followups.errors import (
    TrajectoryChangeMismatchError,
    TrajectoryChangeNotFoundError,
)
from app.application.followups.ports import FollowUpRepositoryPort, TrajectoryChangeRepositoryPort
from app.application.integrity import (
    DuplicateRecordError,
    translating_repository_integrity_errors,
)
from app.domain.follow_up import FollowUp, FollowUpEvidence, FollowUpStatus

# O indice unico parcial da migration 0017. Comparado pelo nome para que uma
# violacao de **outra** restricao (hoje so as PKs) continue subindo como 409 em
# vez de ser confundida com a corrida de abertura. Um driver que nao reporte o
# nome ainda e aceito: a releitura logo abaixo nao acha vencedor nenhum nesse
# caso e o erro sobe do mesmo jeito.
_OPEN_FOLLOW_UP_INDEX = "uq_follow_up_open_per_student_and_owner"


@dataclass(frozen=True)
class OpenFollowUpResult:
    follow_up: FollowUp
    created: bool


class OpenFollowUpService:
    def __init__(
        self,
        trajectory_change_repository: TrajectoryChangeRepositoryPort,
        follow_up_repository: FollowUpRepositoryPort,
    ) -> None:
        self._trajectory_change_repository = trajectory_change_repository
        self._follow_up_repository = follow_up_repository

    def execute(
        self,
        student_id: uuid.UUID,
        trajectory_change_id: uuid.UUID,
        responsible_user_id: uuid.UUID,
    ) -> OpenFollowUpResult:
        change = self._trajectory_change_repository.get_by_id(trajectory_change_id)
        if change is None:
            raise TrajectoryChangeNotFoundError()
        if change.student_id != student_id:
            raise TrajectoryChangeMismatchError()

        existing = self._follow_up_repository.find_open_for_student(student_id, responsible_user_id)
        if existing is not None:
            return self._reuse(existing, trajectory_change_id)

        follow_up = FollowUp(
            id=uuid.uuid4(),
            student_id=student_id,
            status=FollowUpStatus.EM_OBSERVACAO,
            reason=None,
            responsible_user_id=responsible_user_id,
            next_review_date=None,
            created_at=datetime.now(UTC),
        )
        evidence = [
            FollowUpEvidence(
                id=uuid.uuid4(),
                follow_up_id=follow_up.id,
                trajectory_change_id=trajectory_change_id,
            )
        ]
        try:
            with translating_repository_integrity_errors():
                saved = self._follow_up_repository.save_with_evidence(follow_up, evidence)
        except DuplicateRecordError as exc:
            if exc.constraint_name not in (None, _OPEN_FOLLOW_UP_INDEX):
                raise
            # Perdemos a corrida: entre o `find_open_for_student` acima e este
            # INSERT, outra requisicao abriu o acompanhamento deste estudante.
            # A sessao ja foi revertida uma camada abaixo
            # (`repositories/errors.translating_integrity_errors`), entao esta
            # releitura ve a linha vencedora e cai no caminho normal de
            # reaproveitamento.
            winner = self._follow_up_repository.find_open_for_student(
                student_id, responsible_user_id
            )
            if winner is None:
                # Nao ha vencedor para devolver (encerrado no intervalo, ou o
                # indice recusou por outro motivo). Inventar um segundo
                # acompanhamento aqui seria recriar o defeito; o erro sobe.
                raise
            return self._reuse(winner, trajectory_change_id)
        return OpenFollowUpResult(follow_up=saved, created=True)

    def _reuse(self, existing: FollowUp, trajectory_change_id: uuid.UUID) -> OpenFollowUpResult:
        """Devolve o acompanhamento ja aberto, vinculando a mudanca clicada se
        ela ainda nao estiver vinculada. Unico caminho de reaproveitamento —
        alcancado tanto pelo `find_open_for_student` inicial quanto por quem
        perde a corrida no INSERT, para que as duas abas vejam exatamente a
        mesma resposta."""
        linked = {
            item.trajectory_change_id
            for item in self._follow_up_repository.list_evidence_by_follow_up(existing.id)
        }
        if trajectory_change_id not in linked:
            with translating_repository_integrity_errors():
                self._follow_up_repository.add_evidence(
                    FollowUpEvidence(
                        id=uuid.uuid4(),
                        follow_up_id=existing.id,
                        trajectory_change_id=trajectory_change_id,
                    )
                )
        return OpenFollowUpResult(follow_up=existing, created=False)
