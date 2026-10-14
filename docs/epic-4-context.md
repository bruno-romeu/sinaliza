# Epic 4 Context: Acompanhamento Pedagógico

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

This epic turns reviewed trajectory evidence (Epic 3) into a human-conducted process: the coordenação opens a `FollowUp` for a student explicitly from evidence already surfaced in the trajectory, records free-text actions and status transitions as the case progresses, and eventually closes it — all backed by a full, append-only history of actions and evidence that survives closure. It also closes the privacy gap flagged in the professor's review by scoping visibility of a pedagogical observation, once it becomes cited evidence, to the responsible coordinator(s) only. This epic fully realizes UJ-3 and completes RF-18 (Home) by adding the "active follow-ups" section that Epic 3 deliberately left room for.

## Stories

- Story 4.1: Abertura de acompanhamento vinculado a evidências
- Story 4.2: Registro de ações e mudança de status de um acompanhamento
- Story 4.3: Histórico completo de ações e evidências de um acompanhamento
- Story 4.4: Escopo de acesso ao registro pedagógico vinculado a um acompanhamento
- Story 4.5: Acompanhamentos em andamento na página inicial

## Requirements & Constraints

- Opening a follow-up is always an explicit coordenação action from reviewed trajectory evidence — never an automatic classification or a system-initiated case.
- A `FollowUp` is created with status "Em observação", `responsible_user_id` set to the authenticated user, and linked to the triggering `TrajectoryChange`(s) via `FollowUpEvidence` — never with a bare claim lacking traceable evidence.
- Linking evidence to a follow-up is always an explicit coordenação action, never an automatic attach when a new `TrajectoryChange` later appears for an already-open `FollowUp`.
- Status is a closed set of exactly four states (Em observação, Ativo, Aguardando retorno, Encerrado) — never a fifth ad-hoc state (e.g., anything resembling "alto risco"), never free text.
- Status changes happen only through an explicit, closed-set selector (native `<select>` or WAI-ARIA listbox) — never inferred automatically from trajectory signals.
- History (actions and evidence) is append-only and permanent: a new `FollowUpAction` never replaces a prior one, and the full chronological history remains visible even after the follow-up is closed.
- Closing a follow-up with zero recorded actions is allowed (no business-rule block) — transparency is handled by making this visible in the history, not by forced validation. Closing still requires a simple confirmation step (irreversible/destructive action pattern).
- A `PedagogicalObservation` is visible to any authenticated user until it becomes cited evidence (via `TrajectoryChangeSource` → `TrajectoryChange` → `FollowUpEvidence`) of a real `FollowUp`; after that, its text is visible only to the union of `responsible_user_id` across every `FollowUp` that cites it — never exclusive to a single responsible person when multiple follow-ups cite the same record.
- This visibility scoping affects only how the observation's text is displayed/read — it must never filter what the Epic 3 signal evaluators see; convergence detection always runs against the complete, unfiltered set of pedagogical observations.
- The interface still must never show a student ranking, evasion score, or "high-risk students" KPI; a follow-up card never shows an urgency countdown.
- Home's active-follow-ups section shows one card per follow-up with status != Encerrado, with a status pill and student name; empty state is a neutral message ("Nenhum acompanhamento em andamento no momento"), never treated as a system failure.
- Accessibility floor (shared with Epic 3's surfaces) applies to the Tela de Acompanhamento: full keyboard navigation including expanding/collapsing sections and changing status without a mouse, visible focus; nonexistent/removed follow-up shows a factual message with a link back to Home (no dedicated 404 page).
- Microcopy stays factual, never implies a definitive conclusion about the person (e.g., "Acompanhamento encerrado." is fine; anything reading as "caso resolvido" about the student is not).
- Response time budget is 5 seconds max per interaction; responsive across desktop and tablet (shared NFR floor with the rest of the product).

## Technical Decisions

- `FollowUp { id, student_id, status, reason, responsible_user_id, next_review_date, created_at }`, `FollowUpEvidence { id, follow_up_id, trajectory_change_id }`, `FollowUpAction { id, follow_up_id, description, author_user_id, created_at }`.
- `FollowUp.status` is a native Postgres ENUM with exactly the four closed values (`EM_OBSERVACAO`, `ACOMPANHAMENTO_ATIVO`, `AGUARDANDO_RETORNO`, `ENCERRADO`) — never a text column, so a 5th state can't enter even via a direct DB patch. Status transitions happen only through an application-service method — never a direct field assignment from a router.
- `follow_up_action` is backstopped at the database privilege level: the application's Postgres role has `GRANT INSERT, SELECT` but not `UPDATE`/`DELETE` on it — history integrity doesn't rely only on application code discipline.
- `FollowUpEvidence.trajectory_change_id` is a real, `NOT NULL` foreign key — schema-enforced, never optional.
- `FollowUpEvidence` is written only by `application/followup` (never by the Epic 3 trajectory-detection path). This is the single module responsible for explicit evidence attachment, preventing a second, divergent auto-attach implementation from ever existing.
- This epic implements the freeze-on-evidence guard deferred out of Story 3.2: once a `TrajectoryChange` row has at least one `FollowUpEvidence` pointing to it, the trajectory upsert (`ON CONFLICT (student_id, type, period_id) DO ...`) must become `DO NOTHING` instead of `DO UPDATE` — the change is now frozen (description/detected_at/sources stop changing) because a follow-up has already cited it as proof. Concretely: add a `NOT EXISTS (SELECT 1 FROM follow_up_evidence WHERE trajectory_change_id = ...)` guard (or equivalent) to `sqlalchemy_trajectory_change_repository.py`'s upsert, plus the corresponding freeze test that Story 3.2 could not write (no `follow_up_evidence` table existed yet).
- The pedagogical-observation visibility filter lives in one place — the repository-base read method for `PedagogicalObservation` — never inlined per-endpoint; this is the same structural-enforcement pattern (`AD-11`) already used for `dataset_split`/`as_of()` filtering.
- Visibility scoping is a display-time redaction, never an input filter to detection: `SignalEvaluator`/`ConvergenceRule` (Epic 3) always run over the complete, unfiltered set of pedagogical observations, because `TrajectoryChange` is `student_id`-scoped (not `user_id`-scoped) and must be identical regardless of who views it.
- The "coordenação pedagógica" extension of RF-22 (beyond `responsible_user_id`) is explicitly out of scope for this epic — deliberately not a second access rule today, revisit only if the product ever gains multiple real users needing cross-visibility.
- `FollowUp.next_review_date` is read only by a live query inside `GET /home` (`WHERE next_review_date <= as_of()`) — never by a scheduled job/reminder (would violate the no-cron hosting constraint).
- General repo conventions still apply: layered architecture (`domain/` pure, `application/` orchestrates via ports, `presentation/` calls only `application/`); PKs are UUID v4; migrations via Alembic only; error envelope `{ "error": { "code", "message" } }`; frontend types generated from OpenAPI, never hand-transcribed; routes in English, kebab/plural (e.g. `/follow-ups/{id}`); "professor" never appears as a product/code identifier — use `User`/`responsible_user_id`.
- RF-18 (Home) is completed here: this epic adds the active-follow-ups section to the same screen Story 3.3 built for recent changes.

## UX & Interaction Patterns

- Status pill (`followup-status-pill`): rounded-full, bordered, one fill/text pair per state (Em observação, Ativo, Aguardando retorno, Encerrado) — reserved exclusively for follow-up status, never repurposed as a student "level," score, or priority badge.
- Status pill click opens a selector with only the 4 closed states — native `<select>` (free keyboard semantics) or a WAI-ARIA listbox pattern (Esc closes, arrow keys navigate, focus returns to the trigger after selection) — never a free-text field.
- Evidence card is reused from the Trajectory screen on the Tela de Acompanhamento, always fully expanded (never collapsed behind "ver mais"), with a "Ver na trajetória de [aluno]" link back to the Trajectory screen.
- Action/registration form (shared pattern with Lançamento): free-text field + submit button, button disabled while the field is empty — no blank record is ever possible; every submitted action joins the history, never replacing a prior entry.
- Active-follow-up card on Home: status pill + student name, entire card area clickable, opens the Tela de Acompanhamento; never shows an urgency countdown.
- Closing (or any irreversible/destructive status change) requires a simple confirmation step before taking effect.
- Single-column layout, max width 900px, no persistent side navigation — same rule as Home and Trajectory.
- WCAG 2.1 AA (reference, not formal certification) applies to the Tela de Acompanhamento as one of the product's three main screens; full keyboard navigation including expanding/collapsing sections and changing status.

## Cross-Story Dependencies

- Story 4.1 depends on Epic 3's `TrajectoryChange`/evidence UI (Story 3.4) as its entry point — "Abrir acompanhamento" is clicked from reviewed evidence there, and implements the freeze-on-evidence upsert guard that Story 3.2 deliberately deferred.
- Story 4.2 (status transitions, actions) and Story 4.3 (full history view) both build directly on the `FollowUp`/`FollowUpAction`/`FollowUpEvidence` rows Story 4.1 creates.
- Story 4.4's visibility scoping activates only once Story 4.1's evidence-linking occurs (an observation becomes scoped the moment it's cited via `FollowUpEvidence`); it must be implemented as a repository-level read filter without touching Epic 3's detection pipeline.
- Story 4.5 (Home active-follow-ups section) depends on Story 4.1 having created `FollowUp` rows, and completes the same Home screen Story 3.3 built for recent changes — the two sections coexist on one page.
