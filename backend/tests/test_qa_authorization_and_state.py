"""QA adversarial — autorizacao entre usuarios e estado concorrente.

O 403 de escopo por responsavel (`FollowUpAccessDeniedError`) e novo. Este
arquivo tenta contorna-lo por todos os caminhos que leem ou escrevem um
`FollowUp` por id, e depois procura **outros** recursos lidos por id sem
checar quem pede.

Resultado: o escopo nao cede em nenhum dos quatro caminhos, e nenhum outro
recurso por id vaza — porque nenhum outro recurso do dominio escolar tem dono.
Isso esta fixado aqui como invariante, nao so afirmado.

O defeito encontrado nesta superficie e outro (D4): a unicidade de "um
acompanhamento aberto por (estudante, responsavel)" existia so como
`SELECT`-depois-`INSERT` na aplicacao, nunca no banco. Corrigido pela
migration 0017 (`uq_follow_up_open_per_student_and_owner`); os testes do bloco
D4 abaixo guardam tanto a restricao quanto o que a tela ve quando a corrida
acontece.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy import text as sa_text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.follow_up import FollowUpStatus
from app.domain.student import DatasetSplit
from app.domain.trajectory_change import SourceType, TrajectoryChangeType
from app.domain.user import UserRole
from app.infrastructure.db.models import (
    AcademicPeriodModel,
    ClassroomModel,
    FollowUpModel,
    StudentModel,
    TrajectoryChangeModel,
    TrajectoryChangeSourceModel,
    UserModel,
)
from app.infrastructure.repositories.sqlalchemy_follow_up_repository import (
    SqlAlchemyFollowUpRepository,
)
from app.infrastructure.repositories.sqlalchemy_pedagogical_observation_repository import (
    SqlAlchemyPedagogicalObservationRepository,
)
from app.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher

_PASSWORD = "Senha-Correta-123"


def _auth_headers(client: TestClient, user: UserModel) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": user.email, "password": _PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def second_user(db_session: Session) -> UserModel:
    """Uma segunda coordenacao. Producao semeia uma so — esta existe para que
    o escopo por responsavel possa ser atacado de fato."""
    user = UserModel(
        name="Coordenação Dois",
        email="coordenacao-dois@escola.test",
        password_hash=BcryptPasswordHasher().hash(_PASSWORD),
        role=UserRole.COORDENACAO_PEDAGOGICA,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def seeded_trajectory_change(
    db_session: Session,
    seeded_enrolled_student: StudentModel,
    seeded_academic_period: AcademicPeriodModel,
) -> TrajectoryChangeModel:
    change = TrajectoryChangeModel(
        id=uuid.uuid4(),
        student_id=seeded_enrolled_student.id,
        type=TrajectoryChangeType.ATTENDANCE_DROP,
        period_id=seeded_academic_period.id,
        detected_at=datetime(2026, 9, 1, tzinfo=UTC),
        description="Queda de frequência no 3º Bimestre Teste",
    )
    db_session.add(change)
    db_session.commit()
    db_session.refresh(change)
    return change


def _open_follow_up(
    client: TestClient,
    headers: dict[str, str],
    student: StudentModel,
    change: TrajectoryChangeModel,
) -> str:
    response = client.post(
        "/follow-ups",
        headers=headers,
        json={"student_id": str(student.id), "trajectory_change_id": str(change.id)},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ---------------------------------------------------------------------------
# Resultado negativo: o escopo por responsavel nao cede em nenhum caminho
# ---------------------------------------------------------------------------


def test_qa_every_follow_up_route_refuses_a_valid_token_of_another_user(
    client: TestClient,
    seeded_user: UserModel,
    second_user: UserModel,
    seeded_enrolled_student: StudentModel,
    seeded_trajectory_change: TrajectoryChangeModel,
) -> None:
    """Token valido de um recurso nao serve para outro. As quatro rotas que
    tocam um `FollowUp` por id — ler, registrar acao, mudar status — sao
    atacadas com um bearer perfeitamente valido de **outra** coordenacao."""
    owner_headers = _auth_headers(client, seeded_user)
    follow_up_id = _open_follow_up(
        client, owner_headers, seeded_enrolled_student, seeded_trajectory_change
    )
    intruder_headers = _auth_headers(client, second_user)

    attempts = [
        ("GET", f"/follow-ups/{follow_up_id}", None),
        ("POST", f"/follow-ups/{follow_up_id}/actions", {"description": "Liguei para a família."}),
        ("PATCH", f"/follow-ups/{follow_up_id}/status", {"status": "ENCERRADO"}),
        (
            "PATCH",
            f"/follow-ups/{follow_up_id}/status",
            {"status": "ACOMPANHAMENTO_ATIVO"},
        ),
    ]
    for method, path, body in attempts:
        response = client.request(method, path, headers=intruder_headers, json=body)
        assert response.status_code == 403, (method, path, response.text)
        assert response.json()["error"]["code"] == "follow_up_access_denied"

    # E nada mudou do lado do dono.
    owner_view = client.get(f"/follow-ups/{follow_up_id}", headers=owner_headers)
    assert owner_view.status_code == 200
    assert owner_view.json()["status"] == "EM_OBSERVACAO"
    assert owner_view.json()["actions"] == []


def test_qa_nonexistent_follow_up_answers_404_for_a_non_owner_too(
    client: TestClient, second_user: UserModel
) -> None:
    """A ordem das checagens importa: se o 403 viesse antes do 404, um
    nao-responsavel distinguiria "existe e nao e seu" de "nao existe" e teria
    um oraculo de enumeracao de ids."""
    response = client.get(f"/follow-ups/{uuid.uuid4()}", headers=_auth_headers(client, second_user))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "follow_up_not_found"


def test_qa_trajectory_detail_never_leaks_another_users_open_follow_up_id(
    client: TestClient,
    seeded_user: UserModel,
    second_user: UserModel,
    seeded_enrolled_student: StudentModel,
    seeded_trajectory_change: TrajectoryChangeModel,
) -> None:
    """`open_follow_up_id` e o atalho "Ver acompanhamento" da tela de
    trajetoria. Se ele devolvesse o acompanhamento de outra coordenacao, a
    tela ofereceria um link que so pode dar 403 — e revelaria o id."""
    owner_headers = _auth_headers(client, seeded_user)
    follow_up_id = _open_follow_up(
        client, owner_headers, seeded_enrolled_student, seeded_trajectory_change
    )

    response = client.get(
        f"/students/{seeded_enrolled_student.id}/trajectory/detail",
        headers=_auth_headers(client, second_user),
    )
    assert response.status_code == 200, response.text
    assert response.json()["open_follow_up_id"] != follow_up_id
    assert response.json()["open_follow_up_id"] is None


def test_qa_opening_a_follow_up_never_reuses_another_users_case(
    client: TestClient,
    seeded_user: UserModel,
    second_user: UserModel,
    seeded_enrolled_student: StudentModel,
    seeded_trajectory_change: TrajectoryChangeModel,
) -> None:
    """O reaproveitamento de `POST /follow-ups` e escopado por responsavel.
    Se nao fosse, a segunda coordenacao receberia 200 com o id do caso alheio
    — e logo em seguida 403 ao abri-lo."""
    owner_headers = _auth_headers(client, seeded_user)
    owner_follow_up_id = _open_follow_up(
        client, owner_headers, seeded_enrolled_student, seeded_trajectory_change
    )

    response = client.post(
        "/follow-ups",
        headers=_auth_headers(client, second_user),
        json={
            "student_id": str(seeded_enrolled_student.id),
            "trajectory_change_id": str(seeded_trajectory_change.id),
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["id"] != owner_follow_up_id


def test_qa_trajectory_change_of_another_student_is_refused(
    client: TestClient,
    db_session: Session,
    seeded_user: UserModel,
    seeded_enrolled_student: StudentModel,
    seeded_trajectory_change: TrajectoryChangeModel,
) -> None:
    """Abrir acompanhamento cruzando o id de um estudante com a mudanca de
    outro e 422, nao um `FollowUpEvidence` que cita evidencia alheia."""
    other_student = StudentModel(name="Outro Estudante", dataset_split=DatasetSplit.EVAL_DEMO)
    db_session.add(other_student)
    db_session.commit()

    response = client.post(
        "/follow-ups",
        headers=_auth_headers(client, seeded_user),
        json={
            "student_id": str(other_student.id),
            "trajectory_change_id": str(seeded_trajectory_change.id),
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "trajectory_change_mismatch"


# ---------------------------------------------------------------------------
# D4 — a unicidade do acompanhamento aberto, agora no banco (migration 0017)
# ---------------------------------------------------------------------------


def test_qa_the_declared_schema_carries_the_same_index_the_migration_creates(
    db_session: Session,
) -> None:
    """A suite constroi o schema por `Base.metadata.create_all`, nao por
    Alembic (`conftest.py`): o indice declarado em `models.py` e o criado pela
    migration 0017 sao dois textos diferentes que tem de produzir o mesmo
    objeto. Sem esta afirmacao, todos os testes do D4 podem passar contra um
    indice que o banco de producao nao tem.

    A string e identica a afirmada em `test_migrations.py`
    (`test_0017_creates_the_partial_unique_index_and_downgrade_drops_it`) — e
    isso que faz as duas pontas se prenderem uma na outra."""
    indexdef = db_session.execute(
        sa_text(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' "
            "AND indexname = 'uq_follow_up_open_per_student_and_owner'"
        )
    ).scalar_one_or_none()
    assert indexdef == (
        "CREATE UNIQUE INDEX uq_follow_up_open_per_student_and_owner "
        "ON public.follow_ups USING btree (student_id, responsible_user_id) "
        "WHERE (status <> 'ENCERRADO'::follow_up_status)"
    )


def _follow_up_row(student: StudentModel, user: UserModel, status: FollowUpStatus) -> FollowUpModel:
    return FollowUpModel(
        id=uuid.uuid4(),
        student_id=student.id,
        status=status,
        responsible_user_id=user.id,
        created_at=datetime.now(UTC),
    )


def test_qa_database_refuses_two_open_follow_ups_for_the_same_student_and_owner(
    db_session: Session,
    seeded_user: UserModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    """D4, o defeito original: `spec-ui-1` adicionou o reaproveitamento de
    `POST /follow-ups` exatamente porque casos abertos duplicados eram um
    defeito, mas a implementacao era `find_open_for_student` (SELECT) seguido
    de `save_with_evidence` (INSERT) e **nada** no banco. Duas requisicoes que
    leem antes de qualquer uma escrever passavam ambas pela verificacao. O
    botao da tela de trajetoria se desabilita enquanto salva, entao o duplo
    clique numa aba estava coberto -- duas abas na mesma trajetoria nao
    estavam: dois cards identicos na Home, com a evidencia dividida entre eles.

    Este teste e o INSERT direto, contornando o SELECT da aplicacao: a regra
    agora e do banco (`uq_follow_up_open_per_student_and_owner`, migration
    0017), nao da sequencia de chamadas."""
    for _ in range(2):
        db_session.add(
            _follow_up_row(seeded_enrolled_student, seeded_user, FollowUpStatus.EM_OBSERVACAO)
        )
    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize(
    "first_status",
    [FollowUpStatus.EM_OBSERVACAO, FollowUpStatus.ACOMPANHAMENTO_ATIVO],
)
def test_qa_the_index_predicate_covers_every_non_encerrado_status(
    db_session: Session,
    seeded_user: UserModel,
    seeded_enrolled_student: StudentModel,
    first_status: FollowUpStatus,
) -> None:
    """ "Em aberto" nao e so `EM_OBSERVACAO`. `AGUARDANDO_RETORNO` e processo em
    curso como qualquer outro, e o predicado do indice e o complemento de
    `ENCERRADO` justamente para nao depender de uma lista que envelhece."""
    db_session.add(_follow_up_row(seeded_enrolled_student, seeded_user, first_status))
    db_session.commit()

    db_session.add(
        _follow_up_row(seeded_enrolled_student, seeded_user, FollowUpStatus.AGUARDANDO_RETORNO)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_qa_a_closed_follow_up_never_blocks_a_new_one(
    db_session: Session,
    seeded_user: UserModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    """A unicidade e por "estudante com processo em aberto", nao por estudante.
    Um estudante pode ter varios acompanhamentos ao longo do ano -- abriu,
    conduziu, encerrou, meses depois abriu outro. Um indice unico total
    proibiria isso; o parcial nao."""
    for _ in range(3):
        db_session.add(
            _follow_up_row(seeded_enrolled_student, seeded_user, FollowUpStatus.ENCERRADO)
        )
    db_session.add(
        _follow_up_row(seeded_enrolled_student, seeded_user, FollowUpStatus.EM_OBSERVACAO)
    )
    db_session.commit()

    assert (
        db_session.execute(
            select(func.count())
            .select_from(FollowUpModel)
            .where(FollowUpModel.student_id == seeded_enrolled_student.id)
        ).scalar_one()
        == 4
    )


def test_qa_two_coordinations_still_open_separate_cases_for_the_same_student(
    db_session: Session,
    seeded_user: UserModel,
    second_user: UserModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    """`responsible_user_id` faz parte da chave. Sem ele, o indice imporia uma
    regra que ninguem decidiu -- "um acompanhamento por estudante na escola
    inteira" -- e quebraria
    `test_qa_opening_a_follow_up_never_reuses_another_users_case`."""
    for user in (seeded_user, second_user):
        db_session.add(_follow_up_row(seeded_enrolled_student, user, FollowUpStatus.EM_OBSERVACAO))
    db_session.commit()  # nao levanta


def test_qa_losing_the_open_race_returns_the_winner_instead_of_an_error(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    seeded_user: UserModel,
    seeded_enrolled_student: StudentModel,
    seeded_trajectory_change: TrajectoryChangeModel,
) -> None:
    """A corrida das duas abas, de verdade e deterministica.

    A janela e o intervalo entre `find_open_for_student` e
    `save_with_evidence`. Aqui ela e reproduzida fazendo a **primeira** leitura
    devolver `None` embora o acompanhamento ja exista -- que e exatamente o que
    a aba perdedora enxerga quando le antes de a vencedora escrever. O INSERT
    entao bate no indice.

    O que se afirma e o comportamento de tela: a aba perdedora recebe 200 com o
    id do acompanhamento que ganhou a corrida (o caminho de reaproveitamento
    que `spec-ui-1` especificou), nao 409 nem 500 -- e continua existindo **um**
    acompanhamento."""
    headers = _auth_headers(client, seeded_user)
    winner_id = _open_follow_up(client, headers, seeded_enrolled_student, seeded_trajectory_change)

    original = SqlAlchemyFollowUpRepository.find_open_for_student
    blind_reads = {"remaining": 1}

    def _blind_first_read(self, student_id, responsible_user_id):  # type: ignore[no-untyped-def]
        if blind_reads["remaining"]:
            blind_reads["remaining"] -= 1
            return None
        return original(self, student_id, responsible_user_id)

    monkeypatch.setattr(SqlAlchemyFollowUpRepository, "find_open_for_student", _blind_first_read)

    response = client.post(
        "/follow-ups",
        headers=headers,
        json={
            "student_id": str(seeded_enrolled_student.id),
            "trajectory_change_id": str(seeded_trajectory_change.id),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["id"] == winner_id
    assert blind_reads["remaining"] == 0

    open_rows = db_session.execute(
        select(func.count())
        .select_from(FollowUpModel)
        .where(
            FollowUpModel.student_id == seeded_enrolled_student.id,
            FollowUpModel.status != FollowUpStatus.ENCERRADO,
        )
    ).scalar_one()
    assert open_rows == 1
    # A evidencia nao se divide entre dois processos: segue uma so, no vencedor.
    detail = client.get(f"/follow-ups/{winner_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["trajectory_changes"]) == 1


def test_qa_reopening_a_closed_case_over_an_open_one_is_refused_in_the_envelope(
    client: TestClient,
    db_session: Session,
    seeded_user: UserModel,
    seeded_enrolled_student: StudentModel,
    seeded_trajectory_change: TrajectoryChangeModel,
) -> None:
    """`ENCERRADO` nao e terminal: `ChangeFollowUpStatusService` nao tem regra
    de adjacencia, qualquer estado e alvo valido a partir de qualquer outro
    (AD-6). Entao reabrir um encerrado passa a esbarrar no mesmo indice quando
    ja existe outro aberto para o par. Fixado aqui como comportamento
    deliberado -- a resposta e o 409 do envelope de integridade, nao um 500."""
    headers = _auth_headers(client, seeded_user)
    first_id = _open_follow_up(client, headers, seeded_enrolled_student, seeded_trajectory_change)
    assert (
        client.patch(
            f"/follow-ups/{first_id}/status", headers=headers, json={"status": "ENCERRADO"}
        ).status_code
        == 200
    )
    _open_follow_up(client, headers, seeded_enrolled_student, seeded_trajectory_change)

    response = client.patch(
        f"/follow-ups/{first_id}/status",
        headers=headers,
        json={"status": "ACOMPANHAMENTO_ATIVO"},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "duplicate_record"


# ---------------------------------------------------------------------------
# Resultado negativo: o escopo de leitura do registro pedagogico (RF-22)
# ---------------------------------------------------------------------------


def test_qa_observation_cited_as_evidence_is_redacted_for_a_non_owner(
    client: TestClient,
    db_session: Session,
    seeded_user: UserModel,
    second_user: UserModel,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
    seeded_trajectory_change: TrajectoryChangeModel,
) -> None:
    """O texto de uma observacao citada como evidencia de um acompanhamento
    so aparece para o responsavel, e **qualquer** responsavel de um dos
    acompanhamentos que a citam a ve (AD-8) — nao apenas o primeiro.

    Ataca a regra onde ela mora (`get_by_ids`), com as linhas reais que a
    acionam: `TrajectoryChangeSource` -> `TrajectoryChange` ->
    `FollowUpEvidence` -> `FollowUp.responsible_user_id`. Chegar ate aqui
    pela rota exigiria fabricar convergencia de 2 sinais; o que seria testado
    la e a convergencia, nao a redacao."""
    owner_headers = _auth_headers(client, seeded_user)
    secret = "Chegou chorando e a família não atendeu o telefone."
    created = client.post(
        "/pedagogical-observations",
        headers=owner_headers,
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(seeded_classroom.id),
            "text": secret,
            "registers_concern": True,
        },
    )
    assert created.status_code == 201, created.text
    observation_id = uuid.UUID(created.json()["id"])

    db_session.add(
        TrajectoryChangeSourceModel(
            id=uuid.uuid4(),
            trajectory_change_id=seeded_trajectory_change.id,
            source_type=SourceType.PEDAGOGICAL_OBSERVATION,
            source_id=observation_id,
        )
    )
    db_session.commit()

    # O dono abre o acompanhamento: e isso que cria o `FollowUpEvidence` e,
    # com ele, a restricao.
    _open_follow_up(client, owner_headers, seeded_enrolled_student, seeded_trajectory_change)

    repository = SqlAlchemyPedagogicalObservationRepository(db_session)
    for_owner = repository.get_by_ids([observation_id], seeded_user.id)
    for_intruder = repository.get_by_ids([observation_id], second_user.id)

    assert for_owner[0].text == secret
    assert for_intruder[0].text != secret
    assert "restrito ao responsável" in for_intruder[0].text


# ---------------------------------------------------------------------------
# Resultado negativo: nenhum outro recurso por id tem dono a vazar
# ---------------------------------------------------------------------------


def test_qa_resources_read_by_id_without_an_owner_check_have_no_owner_to_leak(
    client: TestClient,
    second_user: UserModel,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    """`GET /classrooms/{id}/students`, `GET /classrooms/{id}/assignments` e
    `GET /students/{id}/trajectory` leem por id sem checar quem pede. Isso e
    correto e nao um buraco: turma, matricula e trajetoria nao tem
    `responsible_user_id` nenhum — o unico recurso com dono no dominio e o
    `FollowUp`, e esse e escopado. O teste fixa a fronteira: se algum destes
    ganhar dono um dia, ele passa a precisar da mesma checagem."""
    headers = _auth_headers(client, second_user)
    for url in (
        f"/classrooms/{seeded_classroom.id}/students",
        f"/classrooms/{seeded_classroom.id}/assignments",
        f"/students/{seeded_enrolled_student.id}/trajectory",
    ):
        assert client.get(url, headers=headers).status_code == 200, url

    for model in (ClassroomModel, StudentModel):
        assert not hasattr(model, "responsible_user_id"), model.__name__


def test_qa_a_tampered_token_signature_is_refused(
    client: TestClient, seeded_user: UserModel
) -> None:
    """Trocar o ultimo caractere da assinatura invalida o bearer — o `sub`
    nao e lido de um JWT nao verificado."""
    headers = _auth_headers(client, seeded_user)
    token = headers["Authorization"].removeprefix("Bearer ")
    head, payload, signature = token.split(".")
    flipped = signature[:-1] + ("A" if signature[-1] != "A" else "B")
    response = client.get("/home", headers={"Authorization": f"Bearer {head}.{payload}.{flipped}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_qa_registered_observation_is_attributed_to_the_bearer_not_the_body(
    client: TestClient,
    seeded_user: UserModel,
    second_user: UserModel,
    seeded_classroom: ClassroomModel,
    seeded_enrolled_student: StudentModel,
) -> None:
    """`author_user_id` vem do `sub` do token. Mandar o campo no corpo nao
    pode forjar autoria de outra coordenacao."""
    response = client.post(
        "/pedagogical-observations",
        headers=_auth_headers(client, seeded_user),
        json={
            "student_id": str(seeded_enrolled_student.id),
            "classroom_id": str(seeded_classroom.id),
            "text": "Entregou a atividade da semana.",
            "author_user_id": str(second_user.id),
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["author_user_id"] == str(seeded_user.id)


def test_qa_follow_up_action_is_attributed_to_the_bearer_not_the_body(
    client: TestClient,
    seeded_user: UserModel,
    second_user: UserModel,
    seeded_enrolled_student: StudentModel,
    seeded_trajectory_change: TrajectoryChangeModel,
) -> None:
    owner_headers = _auth_headers(client, seeded_user)
    follow_up_id = _open_follow_up(
        client, owner_headers, seeded_enrolled_student, seeded_trajectory_change
    )
    response = client.post(
        f"/follow-ups/{follow_up_id}/actions",
        headers=owner_headers,
        json={"description": "Conversei com a turma.", "author_user_id": str(second_user.id)},
    )
    assert response.status_code == 201, response.text
    assert response.json()["author_user_id"] == str(seeded_user.id)


def test_qa_registered_action_appears_in_the_owners_history_immediately(
    client: TestClient,
    seeded_user: UserModel,
    seeded_enrolled_student: StudentModel,
    seeded_trajectory_change: TrajectoryChangeModel,
) -> None:
    """A acao registrada entra no historico da proxima leitura, na ordem
    cronologica, com o id do acompanhamento certo. (Que a tela so a mostre
    apos recarregar e divida ja catalogada, `epic-4-retro-item-16`; o que se
    afirma aqui e o lado do servidor.)"""
    headers = _auth_headers(client, seeded_user)
    follow_up_id = _open_follow_up(
        client, headers, seeded_enrolled_student, seeded_trajectory_change
    )
    for description in ("Primeira conversa.", "Retorno da família."):
        created = client.post(
            f"/follow-ups/{follow_up_id}/actions",
            headers=headers,
            json={"description": description},
        )
        assert created.status_code == 201, created.text

    detail = client.get(f"/follow-ups/{follow_up_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert [action["description"] for action in detail.json()["actions"]] == [
        "Primeira conversa.",
        "Retorno da família.",
    ]
