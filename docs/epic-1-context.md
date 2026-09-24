# Epic 1 Context: Autenticação e Registro da Rotina Pedagógica

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

This epic establishes secure access to the system and captures the raw observable facts of daily school life — attendance, grades, assignment delivery status, and free-text pedagogical observations — for students and classes. These facts are the foundation every later trajectory calculation, change detection, and follow-up depends on: nothing downstream (Epic 3's convergence detection, Epic 4's follow-ups) can exist without reliable, non-duplicated, well-attributed records captured here. This epic fully realizes UJ-2 (the coordinator recording a pedagogical observation during routine practice).

## Stories

- Story 1.1: Autenticação da coordenação pedagógica
- Story 1.2: Registro de presença/falta por turma e data
- Story 1.3: Registro de notas por disciplina e período letivo
- Story 1.4: Cadastro de atividades e registro de status de entrega
- Story 1.5: Registro de observação pedagógica em texto livre

## Requirements & Constraints

- Authentication is mandatory for every route except login; unauthenticated access must redirect to login. Login failures show a factual, non-specific error ("Login ou senha inválidos.") without revealing which field is wrong, and issue no token on failure.
- There is exactly one user profile (Coordenação Pedagógica) — never a second "professor" profile, and the word "professor" must never appear in product or code naming.
- Passwords must be hashed (bcrypt/argon2), never stored in plain text.
- Attendance must be recorded per student, classroom, and date, distinguishing justified vs. unjustified absence. Duplicate attendance for the same student/classroom/date combination must be rejected with a factual inline message and must be structurally impossible, not just application-checked.
- Grades are recorded per subject and academic period on a 0.0–10.0 numeric scale, with no pass/fail semantics. Out-of-range values must be rejected with field-associated validation messaging.
- Assignments are registered against classroom, subject, and academic period; each student's submission status is one of delivered, not delivered, or partial.
- Every pedagogical observation is free text tied to the student, the authoring user, and a creation timestamp — this reference to the origin record is what later lets any derived signal point back to its source (RF-09). An observation not yet cited as evidence for a follow-up is visible to any authenticated user; scoped visibility by responsible user is a rule that only activates once the observation is cited as evidence (implemented in Epic 4, not here).
- Accessibility floor (WCAG 2.1 AA reference, not certification) applies to all forms in this epic: every field has a visible associated label (never placeholder-only), buttons/inputs meet a 44×44px touch target, and validation errors are wired via `aria-describedby` rather than color/icon alone.
- No screen in this epic exists for registering classrooms or students — those come from a development fixture/seed (this epic) or later synthetic generation (Epic 2). There is no class/student CRUD surface in the MVP.
- Response time budget for any interaction is 5 seconds max; interface must be responsive across desktop and tablet.

## Technical Decisions

- Layered architecture: `domain/` is pure Python (no framework imports); `application/` depends only on `domain/` and repository ports; `presentation/` (FastAPI routers) calls only `application/` services, never touching `infrastructure/` or `domain/` directly.
- `User` is a single model with no role enum beyond one fixed value (`COORDENACAO_PEDAGOGICA`); auth is stateless JWT bearer.
- Key entities for this epic (see `docs/data-model.md`): `User`, `Classroom`, `AcademicPeriod`, `Student` (with `dataset_split`, irrelevant until Epic 2/5), `Enrollment`, `AttendanceRecord`, `Grade`, `Assignment`, `AssignmentSubmission`, `PedagogicalObservation`.
- `AttendanceRecord.status` is an enum (`PRESENT`, `ABSENT_JUSTIFIED`, `ABSENT_UNJUSTIFIED`) with a database-level `UNIQUE(student_id, classroom_id, date)` constraint — duplicate prevention must not rely solely on application logic.
- `Grade.value` is `numeric(4,2)` on a 0.0–10.0 scale with no approval/failure field.
- `PedagogicalObservation` has no `follow_up_id` — it belongs to the student, not to any specific follow-up; the visibility-scoping rule referenced by RF-22 is an Epic 4 concern layered on top later, not something to build here.
- General conventions to follow: PKs are UUID v4; migrations via Alembic only (never manual schema edits); error responses use the envelope `{ "error": { "code", "message" } }`; success responses are the raw JSON resource; frontend TypeScript types are generated from the OpenAPI schema, never hand-transcribed.
- Every state mutation goes through an application-service method — never a router assigning fields directly.

## UX & Interaction Patterns

- Every authenticated screen beyond login shows a simple header: the authenticated user's name plus a link back to Home — no persistent side navigation.
- Form fields (login, attendance, grade, assignment, observation) always carry a visible label above the field, never placeholder-only.
- Save buttons follow the standard button component (native `<button>`, visible focus, 44×44px minimum target); a save button stays disabled while its required text field is empty — there is no blank pedagogical observation or blank action.
- Successful saves show a brief, non-blocking text confirmation (e.g., "Registro salvo.") so the coordinator can continue logging the next entry without interruption — never a blocking modal.
- Duplicate-attendance attempts show a factual, field-adjacent message ("Já existe registro de presença para este aluno, turma e data.") rather than a silent failure or generic error.
- The Lançamento (logging) surface for attendance/grade/assignment/observation is treated as a lightweight utility form set, not one of the three visually-invested principal screens (Home, Trajetória, Acompanhamento) — labels and accessibility still apply, but not the full design system investment.

## Cross-Story Dependencies

- Stories 1.2–1.5 all depend on Story 1.1 (authenticated access) and on classrooms/students existing via a development fixture/seed, since there is no in-product class/student registration screen.
- Story 1.5's note that pedagogical-observation visibility scoping (RF-22) only activates once an observation is cited as follow-up evidence is a forward reference to Epic 4 — nothing about that scoping is implemented in this epic.
- All facts recorded here (attendance, grades, assignment submissions, observations) are the direct input to Epic 3's trajectory indicator calculation and convergence-based change detection — this epic must land first, or with compatible fixture data, for Epic 3 to have anything to compute against.
- Epic 2's synthetic dataset generation reuses the same integrity constraints established here (e.g., `UNIQUE(student_id, classroom_id, date)`) and the same `PedagogicalObservation` structure, rather than introducing a parallel schema.
