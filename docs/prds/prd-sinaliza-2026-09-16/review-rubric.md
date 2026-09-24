# PRD Quality Review — prd-sinaliza-2026-09-16

## Overall verdict

This is an unusually disciplined PRD for its shape: a solo-author TCC capstone that must extend an already-approved, board-evaluated requirements document without contradicting it. I verified the preservation claim directly against `Levantamento_Requisitos_Sinaliza.pdf` — every RF-01 through RF-21 and RNF-01 through RNF-07 is a verbatim, correctly-ordered transcription of the approved source, and the count (21 original RFs, 7 original RNFs) matches exactly with no silent additions or drops. The **[NOVO]** items (RF-22, RF-23, RNF-08–14) are traceable one-for-one to `brainstorm-intent.md` with no invention beyond what that session decided. The main risks are not fidelity risks but downstream ones: most of the 21 preserved RFs carry no explicit testable consequence beyond their one-line text (acceptable for several, genuinely underspecified for a couple — grading scale, absence justification codes), and the Vision's central ethical principle ("compared only against own history") is stated with conviction but its enforcement mechanism is deferred entirely to a future UX step, so nothing in this PRD actually blocks a peer-comparison feature from being built by mistake.

## Decision-readiness — strong

Trade-offs are named, not smoothed. §9 Open Questions are genuinely open — e.g. Q1 (hosting vs. cold-start vs. RNF-01's 5-second budget) has no answer baked in, and the PRD explicitly warns "não devem ser assumidas como resolvidas." The `[NOTE FOR PM]` in §2.1 sits at a real tension (coordinator absorbing teacher duties, and why "professor" must never appear in code) rather than at a safe checkpoint. The single `[ASSUMPTION]` (§4.6, indexed in §10) is placed exactly where the approved text is ambiguous ("convergência de sinais" has no defined threshold) rather than smoothed over.

### Findings
- **low** Success metric SM-6 ("sem contradição identificável pela banca") is unfalsifiable as written — there's no criterion for what would count as a contradiction found. *Fix:* either drop SM-6 (redundant with the fidelity check this review already performed) or replace it with a concrete check (e.g., "RF/RNF text diff against the approved PDF shows zero deltas outside renumbering").

## Substance over theater — strong

No persona theater — one profile, and §2.1's clarifying note about absorbed teacher duties is doing real work, not padding. No generic Vision theater: "o aluno é sempre comparado contra o próprio histórico, nunca contra os colegas" is specific enough that it could not swap into an unrelated PRD, and it's threaded through Glossary, RF-11, RNF-08, and the UX note in §4.10 rather than stated once and dropped. NFRs are not boilerplate — RNF-01 gives a number (5s), RNF-08 names a standard (WCAG 2.1 AA) and confines it to three named screens, RNF-10 names three actual browsers. The Success Metrics counter-metrics (SM-C1, SM-C2) are a real forcing function against gaming SM-2/SM-4, not decoration.

No findings — this dimension is earned.

## Strategic coherence — strong

The thesis is explicit and singular: not "who is at risk" but "what changed and why, with evidence" (§1), and it is the actual selection filter behind every feature — RF-11's convergence-not-single-signal rule, RF-21's ban on risk rankings, RF-23's train/eval split existing specifically so the ML score stays an experimental side-channel rather than the product's spine. Success metrics validate the thesis rather than measuring activity: SM-2 checks evidence-traceability (not "detections per week"), SM-3 checks the absence of risk UI in 100% of the demo, and the two counter-metrics exist precisely to stop the thesis from being undermined by proxy optimization (more detections, fancier model). MVP scope logic (§6) reads as "what's needed to prove the thesis defensibly," not "what's easy first."

No findings — this dimension is earned.

## Done-ness clarity — adequate

Mixed picture, and the mix is defensible rather than sloppy. Where the PRD introduces new or ambiguous ground, it adds explicit `**Consequências (testáveis):**` blocks (RF-11, RF-22, RF-23, RNF-08, RNF-09, RNF-11, RNF-13, RNF-14) with concrete, checkable statements ("Nenhum `TrajectoryChange` é exibido sem ao menos um `source_record_id` válido"). Where an RF is preserved verbatim from the approved document and is already self-testable as written (RF-04's duplicate-prevention, RF-07's closed enum, RF-13's closed status set), no elaboration was needed and none was added — correct restraint given the "no reinterpretation" constraint.

But a few preserved RFs are one-liners that are *not* self-testable as stated, and the PRD doesn't flag the gap with an `[ASSUMPTION]` or defer it explicitly:

### Findings
- **medium** RF-05 ("registrar notas de estudantes por disciplina e período letivo") specifies no grading scale, range, or pass/fail semantics (§4.3) — an engineer cannot write an acceptance test from this alone, and nothing in the PRD flags it as deferred to architecture. *Fix:* add an `[ASSUMPTION]` pointing to where the scale gets fixed (architecture/data-model), or confirm `docs/data-model.md` already answers this and cross-reference it here the way RF-11 cross-references it.
- **low** RF-03 (frequency register) doesn't specify whether an absence needs a justification/type code, which affects whether RF-11's "queda de frequência" signal counts justified absences. *Fix:* one sentence noting this is either out of scope for v1 or deferred to architecture, so the gap reads as intentional rather than missed.
- **low** The Vision's core principle (student vs. own history, never peers) has no enforcement FR of its own — it's asserted in §1, echoed in the Glossary and RF-11's consequences, and RF-21 bans risk *rankings* specifically, but nothing explicitly bars a *comparative* (non-ranking) visualization like a cohort-average overlay. The "curva de crescimento pediátrico" metaphor is explicitly deferred to UX (§4.10), meaning the principle's actual technical guardrail doesn't exist yet anywhere in this document. *Fix:* either treat this as consciously deferred (say so) or add a one-line testable consequence under RF-19/RF-21 constraining what the trajectory view is prohibited from rendering, ahead of the UX pass.

## Scope honesty — strong

§5 (Não-Objetivos) and §6.2 (Fora de Escopo) do real work rather than gesturing — each exclusion is tied to a reason and, where relevant, an RNF (e.g., legal-guardian access deferred to RNF-12, not silently dropped). The MoSCoW split in §6.1/§6.2 mirrors `brainstorm-intent.md`'s prioritization exactly, so nothing was quietly upgraded or downgraded between brainstorm and PRD. Open-items density (3 Open Questions, 1 Assumption, 1 NOTE FOR PM) is proportionate — light, matching a document whose core content is largely locked by prior approval, not a green-light-to-build document inventing new scope.

No findings — this dimension is earned.

## Downstream usability — strong

This is the PRD's strongest suit given it explicitly feeds architecture and UX next. Glossary terms (Trajetória, Mudança Relevante, Fator Preocupante, Acompanhamento, Score Experimental, Recorte de Treino/Avaliação) are used identically everywhere they recur, including in `docs/data-model.md`'s entity names (`TrajectoryChange`, `FollowUp`, `source_record_ids`, `responsible_user_id` all appear there matching the PRD's usage). RF IDs are contiguous 01–23 with no gaps or duplicates; RNF IDs are contiguous 01–14. Every cross-reference I traced resolved (RF-22↔RNF-12, RF-23↔RNF-14, §6.2↔RNF-12/13, §9↔RF-16/RF-21). Each of §3–§8 could be pulled out standalone and still make sense via Glossary terms rather than "see above."

No findings — this dimension is earned.

## Shape fit — strong

Correctly calibrated to a solo-operator, chain-top, regulatory-adjacent academic PRD. Three UJs, self-consciously scoped down ("Escopo mais leve que o padrão de PRD, compatível com projeto de TCC de autor único" — §2.4) rather than padded to look thorough; each has a named protagonist (the single role, "a coordenação pedagógica," consistently). No multi-stakeholder UJ apparatus was forced onto a single-operator tool. The "regulatory update" framing (renumbering an approved, board-evaluated document without reopening it) is handled as constraint traceability — the fidelity check in this review confirms it actually holds, not just that the PRD claims it holds. No over- or under-formalization observed.

No findings — this dimension is earned.

## Mechanical notes

- **Verified against source**: Direct comparison against `docs/ulbra-models/Levantamento_Requisitos_Sinaliza.pdf` confirms RF-01–RF-21 and RNF-01–RNF-07 are verbatim transcriptions in original order, with correct counts (21 RFs, 7 RNFs) — the "faithful preservation" claim in the epigraph is not just asserted, it holds under direct check.
- **ID continuity**: RF-01 through RF-23 contiguous, no gaps/dupes. RNF-01 through RNF-14 contiguous, no gaps/dupes.
- **Assumptions Index roundtrip**: Exactly one inline `[ASSUMPTION]` (§4.6/RF-11) and exactly one entry in §10 — matches verbatim. Clean roundtrip.
- **Cross-reference resolution**: All checked cross-references (RF↔RNF, RF↔§6.2, §9↔RF) resolve to real, existing IDs.
- **Glossary drift**: None found within the PRD itself. Note for awareness only: upstream brainstorm material (`brainstorm-intent.md`) calls the ML output "score de risco" while the PRD consistently renames it "Score Experimental" — this reads as a deliberate framing decision (avoiding alarm-language, consistent with RF-16/RNF-14's intent), not accidental drift, since the PRD is internally consistent wherever the term appears.
- **UJ protagonist naming**: All three UJs carry "a coordenação pedagógica" as protagonist inline, consistent with the single-profile shape.
