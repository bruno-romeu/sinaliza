---
title: 'Pacote de backend para o novo design system (acompanhamento duplicado, aluno na trajetória, textos)'
type: 'feature'
created: '2026-10-22'
status: 'review'
baseline_commit: 'e5fc9dfb957b5ebe2e07807c421b6fc5c676dd1e'
route: 'oneshot'
route_source: 'human'
review: 'quick'
review_source: 'auto'
lenses_ran: []
review_loop_iteration: 0
context: ['Design system Sinaliza, seção "Contrato de dados"']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** O novo design system (telas de referência da Home, Trajetória do Estudante e Acompanhamento) depende de três coisas que a API não entrega ou entrega de forma errada:

1. `POST /follow-ups` sempre cria um `FollowUp` novo. Cada clique em "Abrir acompanhamento" (ou uma segunda visita à Trajetória) gera outro caso aberto para o mesmo aluno.
2. `GET /students/{id}/trajectory/detail` não traz nome nem turma do aluno, então a página abre com o título genérico "Trajetória do estudante", e não informa se já existe acompanhamento aberto.
3. Os textos gerados pelo backend usam travessão (proibido na voz do design system), as notas chegam como "4.50" e o fator preocupante começa com "Mudança recente:", o que faz um sinal não confirmado parecer uma mudança.

**Approach:**

1. `OpenFollowUpService` procura um `FollowUp` não encerrado do mesmo aluno e do mesmo responsável. Se existe, reaproveita (HTTP 200) e, se a mudança clicada ainda não está vinculada, adiciona um `FollowUpEvidence`. Se não existe, cria como antes (HTTP 201). Continua sendo sempre um clique explícito (AD-1): nada é vinculado automaticamente.
2. `TrajectoryDetailOut` ganha `student { id, name, classroom_name }` e `open_follow_up_id` (o acompanhamento aberto do usuário que faz a requisição, ou `null`). Ambos opcionais no schema, então o contrato atual não quebra.
3. `build_description` passa a gerar "Queda de frequência e queda de notas no 3º Bimestre" (sem prefixo e sem travessão). Novo `build_concerning_description`: "Sinal isolado: queda de notas no 3º Bimestre". Evidência de nota: "Nota 4,5 em Matemática em 08/09/2026".

</frozen-after-approval>

## Implementation Notes

- Reaproveitamento escopado por `responsible_user_id`, porque as escritas num `FollowUp` são dele (RF-22, epic-4-retro-item-18). Outro usuário que clica abre o próprio acompanhamento.
- Depois de `ENCERRADO`, um novo clique cria um acompanhamento novo; o encerrado continua no histórico.
- `GetStudentTrajectoryDetailService` recebe `student_profile_repository` e `follow_up_repository` como parâmetros opcionais, para não quebrar quem constrói o serviço sem eles.
- `StudentRepository.get_profile` usa o mesmo filtro `EVAL_DEMO` de `get_by_id`; com mais de uma matrícula, vale o ano letivo mais recente.
- Sem migration. Descrições de `TrajectoryChange` já persistidas e congeladas por evidência de acompanhamento mantêm o texto antigo até o dataset ser regerado.
- Ajuste mínimo no frontend atual, para a tela não ficar incoerente com os textos novos até a migração visual: a Home mostra só a descrição (sem repetir o tipo com travessão), o card de evidência não repete a data que já vem na descrição, a Trajetória usa o nome e a turma do aluno no título e troca "Abrir acompanhamento" por um link "Ver acompanhamento" quando `open_follow_up_id` vem preenchido.
- Fica de fora (próximo pacote): bloqueio de corrida em clique duplo simultâneo (o frontend já desabilita o botão durante o envio; um índice único parcial pode vir depois), `classroom_name` nas listas da Home, série por indicador, histórico de status e autor das ações.

## Review Triage Log

- Ainda não revisado.

## Verification

**Commands:**
- `cd backend && uv run pytest tests/test_ui_package_1.py tests/test_convergence_domain.py tests/test_trajectory.py tests/test_trajectory_detail.py tests/test_follow_ups.py -q` -- expected: todos passam; casos novos cobrem reaproveitamento com a mesma mudança (200, uma linha), nova mudança vinculada ao aberto, novo acompanhamento depois de encerrar, escopo por responsável, `student`/`open_follow_up_id` na trajetória, formatação de nota e textos sem travessão.
- `cd backend && uv run pytest -q` -- expected: sem regressões; as 4 falhas de `tests/test_synthetic_dataset_split.py` são as já registradas em `docs/deferred-work.md` (dependem do usuário seed).

- `cd frontend && npm run generate:api-types && npx tsc --noEmit && npm test` -- expected: 47 testes passam, incluindo os dois novos da Trajetória (título com nome e turma, link "Ver acompanhamento").

**Manual checks (if no CLI):**
- Na Trajetória de um aluno com mudança, clicar duas vezes em "Abrir acompanhamento" leva ao mesmo acompanhamento, e a Home lista um só.
