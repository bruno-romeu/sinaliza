# Review: Stack Versions & Hosting Claims — ARCHITECTURE-SPINE.md

**Reviewed:** 2026-09-17
**Target:** `docs/architecture/architecture-sinaliza-2026-09-17/ARCHITECTURE-SPINE.md` — "Stack" table, AD-9, Structural Seed
**Method:** Live web search (WebSearch), September 2026, against each named technology/version and each hosting/free-tier claim. No claim was taken on trust.

## Verdict

Mostly accurate and evidently web-researched (several version numbers match real releases within days/weeks of the document's date), but there are two real defects: **Python 3.13.x is stale** (3.14 has been current for ~11 months), and **Node 22 "LTS" is technically true but is the wrong LTS line to recommend** (it's in Maintenance, not Active, as of Sep 2026). The Oracle Always Free hosting claims in AD-9 are **factually accurate and current** (the 2 OCPU/12GB cut really happened, mid-2026), but the document **understates a serious, well-documented practical risk**: Ampere A1 capacity is reported as "nearly impossible" to provision in most regions in 2026, which would force reliance on the 1 GB fallback VM — a much shakier foundation for Postgres + FastAPI + Nginx than the doc's confident tone suggests.

---

## 1. Language/Framework/DB Versions

| Claim in doc | Verification result | Status |
|---|---|---|
| Python 3.13.x | **Stale.** Python 3.14 released 2025-10-07; as of Sep 2026 latest stable is **3.14.7** (released 2026-08-05), with 3.14.8 expected 2026-10-06. Python 3.13 is now the previous major version (still in bugfix/security support, but no longer "current"). Nothing in the doc justifies staying on 3.13 (e.g., a dependency incompatibility with 3.14) — it reads as an unverified/default assertion, not a researched one. | ⚠️ **Flag — wrong/stale** |
| FastAPI 0.141.x | Confirmed. Latest as of late July 2026 is **0.141.1**. Plausible and current for Sep 2026. | ✅ Verified accurate |
| PostgreSQL 18.6 | Confirmed exactly. **18.6 released 2026-08-13** is genuinely the latest 18.x minor as of the document's date (18.5 was skipped due to a pre-release regression). This is precise enough that it could only come from an actual lookup, not training-data recall. | ✅ Verified accurate, well-researched |
| SQLAlchemy 2.x | Confirmed. Current is **2.0.54** (2026-04-03 release cited; more recent patch activity through Sep 2026). SQLAlchemy 2.1 is in release-candidate stage (2.1.0rc1, 2026-08-31) — no 3.0 exists. Stating "2.x" generically is safe and accurate. | ✅ Verified accurate |
| Alembic 1.x | Confirmed. Current is **1.19.1** (2026-08-08). "1.x" is accurate; no major-version bump pending. | ✅ Verified accurate |
| scikit-learn 1.9.x | Confirmed. Current is **1.9.1**, with 1.9.0 released June 2026 and 1.10 in development. 1.9.1 is the first version supporting Python 3.15 — note this also implicitly argues *against* pinning the backend to Python 3.13 (see above). | ✅ Verified accurate |
| React 19.3.x | Confirmed, and notably current: **React 19.3.0 released 2026-09-09**, only 8 days before this document. Strong evidence of an actual, dated lookup rather than training-data guesswork. | ✅ Verified accurate, well-researched |
| Vite 8.x | Confirmed. Vite 8.0.0 released 2026-03-12; latest is **8.3.0** as of mid-Sep 2026 (Vite 7 still gets backported security/important fixes). | ✅ Verified accurate |
| Node.js 22.x LTS | **Technically true but the wrong recommendation.** As of Sep 2026: Node 22 entered **Maintenance LTS** on 2025-10-21 (EOL 2027-04-30); **Node 24 is the current Active LTS** (became Active LTS 2025-10-28, EOL 2028-04-30); Node 26 is about to become the new Active LTS on 2026-10-28. A greenfield project ("build do frontend") starting in Sep 2026 would normally pin to Node 24, not a maintenance-mode line. Not "wrong" (22 is still supported), but a stale choice presented without justification. | ⚠️ **Flag — stale choice, not "current"** |
| Docker / docker-compose "atual estável" | No pinned version given, so nothing to falsify. Reasonable as written. | ✅ No issue (unpinned) |

**Net on section 1:** 6 of 8 version claims are not just plausible but demonstrably accurate to the week/day, which is strong circumstantial evidence that a real web search underpinned most of the table (the `<!-- Verificado na web em 2026-09-17 -->` comment is credible for those). Python and Node are the exceptions — both default to the previous-generation LTS/stable line without acknowledgment, which looks like an assumption slipped in among otherwise-verified entries.

---

## 2. AD-9 — Oracle Cloud Always Free Hosting Claim

**Claim:** Ampere A1 Always Free cut to 2 OCPU/12GB "after the 2026 cut," `VM.Standard.E2.1.Micro` as fallback, single always-on VM running docker-compose (Postgres + FastAPI + Nginx), no scale-to-zero, no cron keep-warm needed.

- **The 2026 cut is real and accurately described.** Oracle silently reduced Always Free Ampere A1 allowance from 4 OCPU/24GB to **2 OCPU/12GB**, effective **2026-06-15** (1,500 OCPU-hours + 9,000 GB-hours/month, down from 3,000/18,000). Oracle made no public announcement; existing over-limit instances were slated for termination on/after **2026-08-18**. The doc's "2 OCPU/12GB após o corte de 2026" matches this precisely — this is a well-verified, current, non-obvious fact (the kind of thing training data alone would not reliably contain, since it happened mid-2026). ✅
- **E2.1.Micro fallback spec is correct**: 1 OCPU (AMD, burstable to 1/8 baseline), **1 GB RAM**, up to two instances free. ✅ accurate as named — but the doc does not state the 1GB figure explicitly, which matters for the feasibility judgment below.
- **Understated risk: Ampere A1 capacity/provisioning.** Multiple independent 2026 sources report that in most OCI regions, provisioning a *new* Ampere A1 Always Free instance is "nearly impossible" and routinely fails with out-of-capacity errors — this is a widely-known, current pain point, not a rare edge case. AD-9 mentions the E2.1.Micro fallback only as a conditional ("se a Ampere não estiver disponível na região"), framing it as an unlikely contingency, when in practice it may well be the *default* outcome for a new tenancy in Sep 2026. This materially affects the plan's credibility. ⚠️ **Flag — real risk understated**
- **Feasibility of the fallback itself is questionable.** Running Postgres + Uvicorn/FastAPI + Nginx together via docker-compose on a 1 GB RAM VM (plus OS + Docker daemon overhead) is tight even for a ~200-student synthetic dataset. It's not impossible for a low-traffic single-user-class app, but it is a meaningfully different (and riskier — OOM-kill risk, no headroom for Postgres shared_buffers + ML artifact loading) risk profile than the 12 GB primary path, and AD-9 does not discuss this tradeoff or any memory-tuning mitigation (e.g., swap, reduced Postgres shared_buffers, single Uvicorn worker). ⚠️ **Flag — feasibility of fallback not addressed**
- **"No scale-to-zero, no cron keep-warm needed" is architecturally correct** given a real always-on VM (of either shape) — this conclusion holds regardless of which shape is actually available. ✅

**Net on AD-9:** the headline numeric claim is accurate and clearly researched (rare enough fact that it couldn't be recalled from generic training data), but the document is overconfident about actually obtaining Ampere A1 capacity, and doesn't examine whether the stated fallback shape can realistically run the full stack.

---

## 3. PaaS Free-Tier Comparisons (used to justify Oracle over alternatives)

| Claim | Verification | Status |
|---|---|---|
| Render free tier spins down after ~15 min idle, 30-60s cold start | Confirmed current for Sep 2026: free web services spin down after 15 min of no inbound traffic, cold start ~30-60s (roughly "about a minute"). Matches exactly. | ✅ Verified accurate |
| Fly.io dropped free tier for new accounts since Oct 2024 | Confirmed: Fly.io retired free allowances for new orgs as of **2024-10-07**; new signups get a one-time trial (2 machine-hours or 7 days), then require a card. Still true and unchanged as of Sep 2026 — legacy pre-Oct-2024 accounts are grandfathered but not relevant to a new project. | ✅ Verified accurate |
| Neon free tier scale-to-zero wakes in ~300-800ms | Directionally confirmed (Neon docs/benchmarks cite ~300-800ms typical, "a few hundred ms"), but 2026 benchmarks also show a longer tail: median ~568ms, **p95 ~1.06s, worst case ~1.55s**. The doc's range is the common case, not the full distribution — a minor optimism bias, not a factual error. Also worth noting Neon's zero-scale trigger is 5 minutes of idle (not directly stated in the doc, but doesn't contradict it). | ⚠️ Minor — accurate but slightly optimistic (tail latency not mentioned) |
| Supabase free tier pauses after 7 days idle, 10-30s cold start | Confirmed exactly: free projects pause after 7 days of inactivity; first request after pause takes 10-30s to cold-start. | ✅ Verified accurate |

**Net on section 3:** all four comparison claims are essentially correct as of Sep 2026; only the Neon figure slightly undersells worst-case latency, which is a minor nitpick rather than a substantive error, and doesn't change the conclusion (Oracle avoids cold starts entirely; Neon's tail is still much shorter than Render's or Supabase's).

---

## 4. Other Technologies Spotted

- **bcrypt/argon2** (AD-8, password hashing) — both remain current, actively maintained choices in Sep 2026; no issue.
- **JWT bearer stateless auth** — no version/currency claim made, nothing to verify.
- **pydantic-settings** (Consistency Conventions) — no version pinned; still the standard companion to FastAPI/Pydantic v2 in 2026, no issue.
- **DuckDNS** (Deferred section, free dynamic DNS) — still an active, free service as of 2026 based on general web presence; low-stakes claim, not deeply verified given it's explicitly deferred/non-architectural.
- No other named technology in the Stack table, AD-9, or Structural Seed raised concerns beyond what's covered above.

---

## Summary of Flags (by severity)

1. **High** — Python pinned at 3.13.x while 3.14.x (current stable, 3.14.7) has been out for ~11 months as of Sep 2026; no justification given. Contradicts the document's "verified on the web" framing for an otherwise well-researched table.
2. **Medium** — Node.js pinned at "22.x LTS," which is Maintenance LTS as of Sep 2026, not the Active LTS (Node 24, soon Node 26). Still supported, but not the version a fresh project would pick without a stated reason.
3. **Medium-High** — AD-9 treats Ampere A1 unavailability as an edge case ("se não estiver disponível na região"), when multiple 2026 sources describe successful provisioning as the exception, not the rule, in most regions. The plan's primary path may not be obtainable in practice.
4. **Medium** — The 1 GB `VM.Standard.E2.1.Micro` fallback's ability to run Postgres + FastAPI/Uvicorn + Nginx concurrently is asserted implicitly but never examined; this is a materially riskier configuration than the 12 GB primary path and deserves explicit tradeoff discussion (worker counts, shared_buffers tuning, swap).
5. **Low** — Neon cold-start figure (~300-800ms) is accurate for the common case but omits the documented tail (p95 ~1.06s, worst case ~1.55s); doesn't change the hosting decision but is a minor precision gap.

Everything else checked — FastAPI, PostgreSQL, SQLAlchemy, Alembic, scikit-learn, React, Vite, the Oracle "2 OCPU/12GB cut" headline fact, Render/Fly.io/Supabase free-tier claims — is accurate and consistent with a real Sep-2026 web lookup, several to a precision (exact release dates within days) that would be very unlikely from training-data recall alone.
