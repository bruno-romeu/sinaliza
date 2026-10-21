---
title: 'Story 6.2: Provisionamento da VM sempre ativa (Plano A/B)'
type: 'feature'
created: '2026-10-20'
status: 'done'
baseline_commit: 'cb6fe5bfb230ef9c513add2a914105dd5ddd9524'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context: ['{project-root}/docs/epic-6-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 6.1 produced a `docker compose up --build` that packages the three services, but nothing documents or scripts *how to get a VM to run it on* — no Oracle Cloud provisioning steps, no Plan A→B capacity-fallback decision procedure (AD-9), no Postgres/swap tuning for Plan B's 1GB RAM budget, and no way to verify the deployed system stays always-on (RNF-04) and meets the 5-second response guarantee (RNF-01).

**Approach:** Produce a human-executable provisioning runbook (Oracle Cloud console steps for Plan A, capacity-failure fallback to Plan B, SSH/Docker bootstrap, deploy) plus the Plan B tuning config (reduced Postgres `shared_buffers` + swap) and two verification scripts (always-on/no-scale-to-zero checklist, RNF-01 5-second smoke test) a human operator runs against the real VM once provisioned. No cloud account exists in this environment — this story delivers the runbook/scripts/config, not a live deployment.

## Boundaries & Constraints

**Always:**
- Document Plan A (Ampere A1) as the attempted-first path and Plan B (`VM.Standard.E2.1.Micro`) as an equally-expected fallback on capacity failure, never framed as a last resort (AD-9).
- Plan B config reduces Postgres `shared_buffers` below the image default, keeps the single Uvicorn worker already fixed by spec-6-1, and enables swap.
- Deploy steps reuse Story 6.1's `docker-compose.yml` unmodified (`docker compose up --build -d`) — this story configures the host, not the containers.
- Verification tooling is runnable by a human against a real VM (plain `bash` + `curl`/`ssh`, no new dependency to install beyond what the runbook itself provisions).

**Never:**
- No actual Oracle Cloud provisioning happens in this session (no credentials exist) — do not fabricate having provisioned or deployed anything.
- No changes to `docker-compose.yml`, `backend/`, or `frontend/` application code — this story is host-level config and operator docs only.
- No scheduled/cron keep-warm mechanism, anywhere (would itself violate the no-cron constraint, AD-9/RNF-06).
- No Plan C (Render/Neon/Vercel) content — that is Story 6.3.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Plan A capacity available | Operator requests Ampere A1 shape in OCI console | Runbook's Plan A steps provision a 2 OCPU/12GB instance; Plan B steps are skipped | N/A |
| Plan A capacity exhausted (`Out of host capacity`) | OCI console/CLI returns a capacity error on Ampere A1 create | Runbook directs operator straight to Plan B steps (`VM.Standard.E2.1.Micro`), applies the shared_buffers + swap config | None — documented as an expected, equally-valid path, not a crash |
| Plan B VM provisioned | 1 OCPU / 1GB RAM instance up | `deploy/postgres-plan-b.conf` is mounted into the `postgres` service; `deploy/enable-swap.sh` run once over SSH before `docker compose up` | If swap is skipped, runbook calls out the OOM risk explicitly |
| VM reboots or a container crashes | Host restart / `docker kill` on any of the 3 containers | `deploy/verify-always-on.sh` reports all 3 containers `Up`/`running` with `restart: unless-stopped` honored, no scale-to-zero | Script exits non-zero and names the failing container if one does not recover |
| Response-time check | `deploy/smoke-test.sh <base-url>` against the live system | Each checked endpoint responds within 5s; script prints per-request latency and a pass/fail summary | Any request over 5s or a connection error fails the script with a non-zero exit and names the offending URL |

</frozen-after-approval>

## Code Map

- `docker-compose.yml` -- spec-6-1's compose file; the Plan B override is applied via an operator-created `docker-compose.override.yml` that adds an inline `command: ["postgres", "-c", "shared_buffers=64MB", ...]` to the `postgres` service — no config-file mount or extra `volumes` entry is used — reuse as-is, do not edit its service definitions (this story only documents an operator-applied override, see Design Notes for the exact mechanism chosen).
- `backend/.env.example` -- the single source of env vars Compose reads (`POSTGRES_*`, `JWT_SECRET`); the runbook's deploy step tells the operator to copy this to a root `.env` on the VM, matching spec-6-1's documented convention.
- `docs/epic-6-context.md` -- AD-9 Plan A/B/C tiering, RNF-01 (5s), RNF-04 (always-on, no scale-to-zero), no-cron constraint; this spec implements the Plan A/B half only.
- `docs/architecture/architecture-sinaliza-2026-09-17/ARCHITECTURE-SPINE.md:107-115` (AD-9) -- exact shape names, RAM figures, and the "Plan B is equally expected, not last resort" framing to preserve verbatim in the runbook.
- No existing `deploy/`, `scripts/`, or `ops/` directory in the repo — this story introduces `deploy/` at the repo root as the home for provisioning/operator assets, alongside root-level `docker-compose.yml`.

## Tasks & Acceptance

**Execution:**
- [ ] `deploy/vm-provisioning-runbook.md` -- step-by-step Oracle Cloud Always Free provisioning guide: create tenancy/compartment, attempt Ampere A1 (Plan A) create, on capacity failure fall back to `VM.Standard.E2.1.Micro` (Plan B), open security-list ports 22/80, SSH in, install Docker + Compose plugin, `git clone`, copy `backend/.env.example` to root `.env`, apply Plan B tuning if applicable, `docker compose up --build -d` -- gives a human operator everything needed to reproduce Stories 6.1+6.2 on a real VM
- [ ] `deploy/postgres-plan-b.conf` -- Postgres config fragment for the 1GB-RAM Plan B host: `shared_buffers = 64MB` (below the 128MB image default), `work_mem = 4MB`, `max_connections = 20`, each line commented with its rationale -- satisfies the "reduced shared_buffers" AC
- [ ] `deploy/enable-swap.sh` -- idempotent bash script: checks for an existing swapfile, else creates a 2GB `/swapfile`, `mkswap`, `swapon`, persists via `/etc/fstab` entry (skipped if already present) -- satisfies the "swap enabled" AC for Plan B
- [ ] `deploy/verify-always-on.sh` -- bash script taking an SSH host (or run locally on the VM): runs `docker compose ps` and asserts all 3 services show `Up`/`running` and `restart: unless-stopped` policy (via `docker inspect --format`), prints a clear pass/fail -- satisfies the "always active, no scale-to-zero" AC
- [ ] `deploy/smoke-test.sh` -- bash script taking a base URL: `curl`s the frontend root and a representative `/api/*` route, times each with `curl -w '%{time_total}'`, fails if any exceeds 5s or returns a non-2xx/3xx -- satisfies the RNF-01 5-second AC
- [ ] `deploy/README.md` -- short index pointing at the runbook and each script, noting this is Plan A/B tooling (Plan C is Story 6.3) -- orientation for a future reader of `deploy/`

**Acceptance Criteria:**
- Given the runbook, when Plan A capacity fails, then the documented next step is Plan B provisioning, not a dead end or a "contact support" instruction (AD-9)
- Given `deploy/postgres-plan-b.conf`, when compared to the Postgres image default, then `shared_buffers` is set below the 128MB default (AD-9)
- Given `deploy/enable-swap.sh`, when run twice in a row, then the second run detects existing swap and makes no duplicate changes (idempotency)
- Given `deploy/verify-always-on.sh`, when run against a `docker compose up -d` stack with `restart: unless-stopped` on all 3 services, then it reports pass; when a service lacks that policy, it reports fail and names the service
- Given `deploy/smoke-test.sh <url>`, when every checked request completes under 5s, then it exits 0; when any exceeds 5s or errors, it exits non-zero and names the failing URL (RNF-01)
- Given none of the new scripts, when inspected, then none installs or invokes a cron job, systemd timer, or scheduled task — swap and config are one-time setup actions a human runs manually (RNF-06, AD-9)

## Implementation Notes

Implemented all six files under `deploy/` as scoped. Verified scripts with `bash -n` (no syntax errors; `shellcheck` unavailable in this environment). Ran the real `docker compose up --build` stack locally to exercise `verify-always-on.sh`'s fail path: it correctly detected and named `backend` when it failed to start due to a pre-existing CRLF line-ending issue in `backend/docker-entrypoint.sh` (unrelated to this story, out of boundary — `backend/` changes are explicitly out of scope — flagged below, not fixed). Built a disposable busybox-based fixture outside the repo (3 services, varying restart policies) to exercise `verify-always-on.sh`'s pass path and its restart-policy fail path directly, since the real stack couldn't reach a healthy state. For `smoke-test.sh`, switched the representative `/api/*` check from `/api/auth/login` (always non-2xx without live credentials) to `/api/openapi.json` (FastAPI's only unauthenticated route, confirmed via `backend/app/main.py` router wiring), verified both pass and connection-refused cases against local stub servers. Confirmed no cron/systemd/scheduled-task mention appears except as explicit negative documentation.

**Known pre-existing issue surfaced, not fixed (out of this story's boundary):** `backend/docker-entrypoint.sh` fails to exec when `docker compose up --build` is run from this Windows checkout (`exec ./docker-entrypoint.sh: no such file or directory`), because the Windows working tree checks it out with CRLF (`core.autocrlf=true` locally) and the repo has no `.gitattributes` to prevent that. Verified the committed git blob itself is clean LF (`git cat-file -p HEAD:backend/docker-entrypoint.sh` has zero `\r` bytes), so this does not affect the real Ubuntu/Linux VM target this story's runbook provisions — it only blocked an end-to-end real-stack local run of `smoke-test.sh`'s happy path on this Windows machine. Logged in `docs/deferred-work.md` as a low-priority Windows-local-dev convenience fix.

## Spec Change Log

## Review Triage Log

Lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment. Verdicts: 10 patch, 3 defer, 3 reject (1 false/premature, 2 low-reject).

| Finding | Verdict | Evidence |
|---|---|---|
| All three new scripts (`enable-swap.sh`, `verify-always-on.sh`, `smoke-test.sh`) are committed non-executable (`100644`), but the runbook/README invoke two of them (`verify-always-on.sh`, `smoke-test.sh`) as `./deploy/....sh` with no `chmod +x` step | patch | Verified: `git diff` shows `new file mode 100644` for all three; runbook only has `chmod +x deploy/enable-swap.sh` (step 8b), none for the other two. As written, Section 10's commands fail with "Permission denied." |
| Code Map's `docker-compose.yml` bullet says the Plan B override works "via a bind-mounted `command: postgres -c config_file=...` or an extra `volumes` entry" — stale relative to Design Notes and the actual implementation, which uses neither (inline `-c shared_buffers=...` command args, no config file or mount) | patch | Verified by direct read: Design Notes and `deploy/vm-provisioning-runbook.md`'s `docker-compose.override.yml` snippet both use `command: ["postgres", "-c", "shared_buffers=64MB", ...]` with no `config_file` or `volumes:` entry anywhere. Code Map line was my own planning-time guess, superseded during implementation but never updated. |
| `verify-always-on.sh`'s `run()` never `cd`s into the compose project directory; the documented remote invocation (`./deploy/verify-always-on.sh ubuntu@<ip>`) runs `docker compose ps` in the SSH login shell's default directory, not the `~/sinaliza` clone the runbook creates | patch | Verified by direct read of `run()` (plain `ssh "${SSH_HOST}" "$1"`, no `cd`) and the runbook's clone step (`git clone <repo-url> sinaliza`). An SSH login shell defaults to `$HOME`, not `$HOME/sinaliza`, so `docker compose ps` there reports "no configuration file provided" — the one documented remote-verification path as written would fail. |
| `enable-swap.sh`'s `dd` fallback path hardcodes `count=2048` instead of deriving it from the `SWAPSIZE="2G"` variable a line above | patch | Verified: today `2048` MiB == `2G` so it's not a live bug, but it's a second, unenforced source of truth — editing `SWAPSIZE` alone silently desyncs the fallback path on filesystems without `fallocate`. Trivial direct fix (compute the count from `SWAPSIZE`). |
| `smoke-test.sh`'s latency check doesn't validate `TIME_TOTAL` is numeric before the `awk` comparison; an empty/non-numeric value is treated as `0`, producing a false pass | patch | Verified: `awk -v t="${TIME_TOTAL}" ... (t > th)` evaluates a non-numeric `t` as `0` in awk, which is never `> 5`. Low-probability trigger (would need curl's `-w` output to not match the `grep -o 'TIME:[0-9.]*'` pattern despite a successful request) but the guard is a trivial one-line addition. |
| `verify-always-on.sh`'s `ssh` call has no connect timeout, so an unreachable or firewalled VM hangs the script indefinitely instead of failing with a clear error | patch | Verified: `run()`'s `ssh "${SSH_HOST}" "$1"` has no `-o ConnectTimeout`/`-o BatchMode`. Trivial one-line flag addition closes it. |
| Runbook Section 5 uses an explicit `-i ~/.ssh/id_ed25519` for the initial SSH login, but Section 10's `verify-always-on.sh ubuntu@<ip>` invocation has no way to pass a key, silently relying on ssh-agent/default-identity resolution | patch | Verified by direct read of both runbook sections. Real inconsistency for any operator not using the default key filename or an `~/.ssh/config` `Host` alias. Direct fix: one documentation sentence recommending an `~/.ssh/config` entry (or noting the default-key assumption) before Section 10. |
| Runbook's Plan A→B fallback (Sections 2–3) doesn't mention cleaning up/terminating a failed Ampere A1 instance before creating the same-named `sinaliza-vm` Plan B instance | patch | Verified by direct read: no cleanup step exists between the two sections. A plausible naming collision / leftover resource for an operator following the happy-path reading. Direct one-sentence addition to Section 3. |
| The Plan B `docker-compose.override.yml` the runbook has the operator hand-create on the VM is not added to `.gitignore`, risking an accidental `git add -A`/`git commit` of Plan-B-specific tuning into the shared repo | patch | Verified: `.gitignore` has no `docker-compose.override.yml` entry (confirmed by direct grep). Trivial one-line addition, consistent with how `.env` is already gitignored for the same class of host-local file. |
| Runbook Section 0 (Prerequisites) doesn't mention that `curl` (for `smoke-test.sh`) and an SSH client (for `verify-always-on.sh`'s remote mode) must be available on the operator's machine | patch | Verified by direct read of Section 0 — only an OCI account, an SSH key pair, and the repo are listed. Both are real implicit dependencies for the verification tooling the runbook instructs the operator to run in Section 10. Trivial one-line addition. |
| The spec's own `## Verification` section lists the original real-stack commands as the check to run, without noting (as `## Implementation Notes` does) that they could not be run as literally written in this session due to the CRLF/`docker-entrypoint.sh` blocker — a reader skimming only `## Verification` could believe the real-stack run succeeded | patch | Verified: `## Verification`'s commands section has no pointer to the caveat `## Implementation Notes` already documents. Direct one-line addition cross-referencing the two sections closes the ambiguity. |
| `verify-always-on.sh`, `smoke-test.sh`, and `enable-swap.sh` have no committed, reproducible fixture exercising their actual logic (parsing, idempotency) — this session's validation used an ephemeral busybox fixture and local stub servers that aren't part of the diff and can't be rerun by a future reader; only `bash -n` (syntax only) is committed evidence | defer | Verified: `## Implementation Notes` itself describes the fixtures as built "outside the repo" / "in scratchpad" and not committed. A future logic regression in any of the three scripts (format-string change, case-pattern change, fstab-anchor change) would pass `bash -n` and ship with zero evidence of having been exercised. Fixing this properly means committing a lightweight multi-container fixture under `deploy/` — more than a trivial patch, and this project has no CI/operator-script test harness by design (Epic 6 context: "VM monitoring is SSH + logs only"). Logged to `docs/deferred-work.md`. |
| `docs/sprint-status.yaml`'s `6-2-...` key is `in-progress` while the spec frontmatter is already `status: in-review` with Implementation Notes/Verification filled in | false | Not a defect: this is the workflow's normal mid-run state — step-05 (present) syncs `sprint-status.yaml` to `review` only after this review step completes, per this workflow's own staged design (`sync-sprint-status.md`). Checked again after this review pass, before step-05 runs. |
| `verify-always-on.sh`'s `docker compose ps -q ${svc}` could return multiple container IDs if a service were ever scaled, breaking the single-ID `docker inspect` call | low, reject | Verified unreachable under this project's fixed topology: AD-9/AD-3 require exactly one container per service (single Uvicorn worker, no scaling), and no `deploy: replicas` or `--scale` appears anywhere in `docker-compose.yml` or the runbook. Fix would add complexity (`head -n1`) for a scenario this architecture forbids. |
| `smoke-test.sh`'s representative `/api/*` check uses `/api/openapi.json` (unauthenticated) instead of an authenticated business route, narrowing what RNF-01's 5-second guarantee is actually measured against | low, reject | Verified as a disclosed, reasoned trade-off, not an oversight: the script's own comment and `## Implementation Notes` explain `/api/auth/login` was rejected because it needs live demo credentials a generic operator script can't carry. The AC's literal wording ("a representative /api/* route") is satisfied, and the alternative fix (threading credentials into the script) adds complexity disproportionate to the benefit for a one-off manual check. |

## Design Notes

**Plan B Postgres override mechanism:** `docker-compose.yml` ships the vanilla `postgres:16-alpine` image unmodified (no Plan B knowledge baked in, since most deployments will be Plan A). The `postgres:16-alpine` entrypoint does not auto-load arbitrary mounted `.conf` files, so rather than fight that, the runbook directs the Plan B operator to create a small `docker-compose.override.yml` (which Compose merges automatically, no edit to the committed `docker-compose.yml`) that adds a `command: ["postgres", "-c", "shared_buffers=64MB", "-c", "work_mem=4MB", "-c", "max_connections=20"]` line to the `postgres` service. `deploy/postgres-plan-b.conf` is the single documented source of truth for those three values and their rationale — a human copies them into the override (or the runbook's shown snippet), it is not parsed by any script. This keeps Story 6.1's compose file untouched, per this story's own boundary.

**Idempotency choice for swap:** `enable-swap.sh` checks `swapon --show` and the presence of `/swapfile` before acting, matching common Ubuntu/OCI-image swap-setup convention, so repeated runs (e.g. after a VM reboot during testing, or operator re-running the runbook) are safe.

**Verification scripts run from the operator's machine, not committed as CI:** per Epic 6 context ("VM monitoring is SSH + `docker compose logs` only; no observability dashboard is in scope"), both scripts are plain bash invoked manually or over SSH — no GitHub Actions workflow is added.

## Verification

Note: the real-stack commands below could not be run as literally written in this session — see `## Implementation Notes` for the `backend/docker-entrypoint.sh` CRLF blocker and how verification was actually carried out.

**Commands:**
- `bash -n deploy/enable-swap.sh deploy/verify-always-on.sh deploy/smoke-test.sh` -- expected: no syntax errors
- `shellcheck deploy/*.sh` (if available) -- expected: no errors (warnings acceptable)
- `docker compose -f docker-compose.yml up --build -d && bash deploy/verify-always-on.sh` (run locally, since no real VM exists in this environment) -- expected: reports all 3 services `Up` with `restart: unless-stopped`
- `bash deploy/smoke-test.sh http://localhost` (against the local compose stack) -- expected: both checked requests complete under 5s, script exits 0
- `docker compose down` -- cleanup after local verification

**Manual checks (if no CLI):**
- Read `deploy/vm-provisioning-runbook.md` end-to-end and confirm every step has a concrete command or console action, Plan A→B fallback is unambiguous, and no step requires a scheduled job.
- Confirm `deploy/postgres-plan-b.conf`'s `shared_buffers` value is below Postgres's documented 128MB image default.
