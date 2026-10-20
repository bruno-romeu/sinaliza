# VM Provisioning Runbook — Plan A / Plan B (Story 6.2)

Step-by-step guide for a human operator to provision an always-on Oracle
Cloud VM and deploy the Sinaliza stack on it. This runbook implements AD-9:
Plan A (Ampere A1) is attempted first; Plan B (`VM.Standard.E2.1.Micro`) is
an **equally expected fallback**, not a last resort — multiple 2026 reports
show Ampere A1 capacity failing for new tenancies in most regions. If Plan A
fails, continue straight to Plan B below; do not stop or contact support.

Plan C (Render/Neon/Vercel contingency) is out of scope here — see Story 6.3.

No cloud account exists in the environment this runbook was written in. No
step in this document installs a cron job, systemd timer, or scheduled
task — swap and config changes are one-time, human-run actions (RNF-06).

---

## 0. Prerequisites

- An Oracle Cloud account with Always Free eligibility (new or existing
  tenancy with Always Free resources not yet consumed).
- A local SSH key pair (`ssh-keygen -t ed25519` if you don't have one).
- This repository cloned locally (to push to the VM) or accessible via a
  Git remote the VM can `git clone`.
- `curl` and an SSH client available on your local operator machine —
  `deploy/smoke-test.sh` requires `curl`, and `deploy/verify-always-on.sh`'s
  remote mode (Section 10) requires `ssh`.

---

## 1. Create tenancy / compartment

1. Sign in to the [OCI Console](https://cloud.oracle.com/).
2. Use the root compartment, or create a dedicated compartment for this
   project: **Identity & Security → Compartments → Create Compartment**
   (name: `sinaliza`, parent: root).
3. Note your **region** — Ampere A1 capacity varies by region, and if Plan A
   fails you may want to try a second home region before falling back to
   Plan B (optional; Plan B works in any region).

---

## 2. Plan A — attempt Ampere A1 (preferred path)

1. **Compute → Instances → Create Instance**.
2. Name: `sinaliza-vm`. Compartment: the one from Step 1.
3. **Image and shape**:
   - Image: **Ubuntu 22.04** (or latest Ubuntu LTS available under Always
     Free).
   - Shape: click **Change Shape** → **Ampere** → `VM.Standard.A1.Flex`.
   - Set **2 OCPUs / 12 GB memory** (the Always Free Ampere allotment).
4. **Networking**: use an existing VCN or let the console create a new one
   with a public subnet. Ensure **"Assign a public IPv4 address"** is
   checked.
5. **Add SSH keys**: paste your public key (`~/.ssh/id_ed25519.pub`) or
   upload the `.pub` file.
6. Leave boot volume at default (46–50 GB is fine for Always Free).
7. Click **Create**.

**If the instance provisions successfully:** note the public IP address and
skip to [Section 4 (Open security-list ports)](#4-open-security-list-ports-both-plans).
Plan B steps below are not needed.

**If you see an error containing `Out of host capacity`** (or the instance
goes to a failed/terminated state with a capacity-related reason): this is
the expected, documented outcome in many regions in 2026. **Do not retry
indefinitely or treat this as blocking** — proceed directly to Plan B below.

*(Optional before falling back: you may try a different Availability Domain
within the same region, or try a different home region if your tenancy
permits multiple regions. This is a time-boxed optional retry, not a
required step — if it doesn't succeed quickly, move to Plan B.)*

---

## 3. Plan B — `VM.Standard.E2.1.Micro` fallback (equally valid path)

If Plan A left a failed/terminated `sinaliza-vm` instance visible in the
console, terminate/delete it first so the Plan B instance below can reuse
the same name without a conflict.

1. **Compute → Instances → Create Instance**.
2. Name: `sinaliza-vm`. Compartment: same as above.
3. **Image and shape**:
   - Image: **Ubuntu 22.04**.
   - Shape: **Change Shape** → **Virtual Machine** → `VM.Standard.E2.1.Micro`
     (1 OCPU, 1 GB RAM — part of the Always Free tier, always available,
     no capacity contention).
4. **Networking**: same as Plan A — public subnet, public IPv4 assigned.
5. **Add SSH keys**: same as Plan A.
6. Click **Create**. This shape does not experience the capacity failures
   Ampere A1 does, so this step should succeed.
7. Note the public IP address.

**Plan B requires two additional steps later in this runbook** (marked
**[Plan B only]** below): applying `deploy/postgres-plan-b.conf`'s tuning
via a Compose override, and running `deploy/enable-swap.sh`.

---

## 4. Open security-list ports (both plans)

1. In the OCI Console, go to the VCN used by your instance:
   **Networking → Virtual Cloud Networks → (your VCN) → Security Lists →
   Default Security List**.
2. **Add Ingress Rules**:
   - Source CIDR: `0.0.0.0/0`, IP Protocol: TCP, Destination Port: `22`
     (SSH) — likely already present by default.
   - Source CIDR: `0.0.0.0/0`, IP Protocol: TCP, Destination Port: `80`
     (HTTP, served by the `frontend`/Nginx container).
3. Save.
4. If Ubuntu's own firewall (`ufw`) is active on the instance, also allow it
   there once connected (Section 5): `sudo ufw allow 22,80/tcp`.

---

## 5. SSH in and install Docker + Compose plugin

```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@<VM_PUBLIC_IP>
```

On the VM:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official apt repository
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install Docker Engine + the Compose plugin (gives you `docker compose`)
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Allow running docker without sudo (log out/in after this)
sudo usermod -aG docker $USER
```

Log out and back in (or run `newgrp docker`) so the group change takes
effect, then verify:

```bash
docker --version
docker compose version
```

---

## 6. Clone the repository

```bash
git clone <your-repo-url> sinaliza
cd sinaliza
```

---

## 7. Configure environment

```bash
cp backend/.env.example .env
nano .env   # or vim/vi — edit as needed
```

At minimum, set a real `JWT_SECRET` (long random value — `docker-compose.yml`
requires it to be set, there is no default). Review `POSTGRES_USER`,
`POSTGRES_PASSWORD`, and `POSTGRES_DB` as well; the defaults in
`docker-compose.yml` (`sinaliza`/`sinaliza`/`sinaliza`) are fine for a demo
but should be changed for anything beyond that.

This `.env` at the repo root is auto-loaded by `docker compose` — no other
env file is needed (see `backend/.env.example`'s own header comment).

---

## 8. [Plan B only] Apply Postgres tuning + enable swap

Skip this entire section if you provisioned Plan A (Ampere A1, 12GB RAM) —
the image defaults are sufficient there.

### 8a. Postgres override

`docker-compose.yml` (from Story 6.1) is intentionally left unmodified — it
ships the vanilla `postgres:16-alpine` image, which does not auto-load
arbitrary mounted `.conf` files. Instead, create a
`docker-compose.override.yml` next to `docker-compose.yml` (Compose merges
`docker-compose.override.yml` automatically — no edit to the committed
file):

```yaml
# docker-compose.override.yml — Plan B only. Not committed to the repo;
# created once, by hand, on the Plan B VM. Values match
# deploy/postgres-plan-b.conf (the documented source of truth).
services:
  postgres:
    command:
      - postgres
      - -c
      - shared_buffers=64MB
      - -c
      - work_mem=4MB
      - -c
      - max_connections=20
```

See `deploy/postgres-plan-b.conf` for the rationale behind each value.

### 8b. Enable swap

```bash
chmod +x deploy/enable-swap.sh
./deploy/enable-swap.sh
```

This creates a 2GB `/swapfile`, activates it, and persists it via
`/etc/fstab` — safe to re-run (it detects existing swap and does nothing on
a second run). **If you skip this step**, the 1GB Plan B host has no
headroom for the Postgres + Uvicorn + in-memory ML artifact footprint and
is at meaningful risk of an OOM kill under load — do not skip it on Plan B.

---

## 9. Deploy

```bash
docker compose up --build -d
```

This reuses Story 6.1's `docker-compose.yml` unmodified (with
`docker-compose.override.yml` additionally applied on Plan B, per Step 8a).
All three services start with `restart: unless-stopped`, so they recover
automatically from a VM reboot or container crash without any supervisor
or cron job.

Check status:

```bash
docker compose ps
```

---

## 10. Verify

The commands below assume `ssh` resolves `ubuntu@<VM_PUBLIC_IP>` using your
default identity (ssh-agent or `~/.ssh/id_rsa`/`~/.ssh/id_ed25519`); if you
used a non-default key as in Section 5, add a `Host` alias for it in
`~/.ssh/config` first, since `verify-always-on.sh` has no flag to pass `-i`.

From your local machine (or on the VM itself):

```bash
# Confirm all 3 services are Up with restart: unless-stopped honored
./deploy/verify-always-on.sh ubuntu@<VM_PUBLIC_IP>
# or, run directly on the VM:
./deploy/verify-always-on.sh

# Confirm RNF-01: responses complete within 5 seconds
./deploy/smoke-test.sh http://<VM_PUBLIC_IP>
```

Both scripts print a pass/fail summary and exit non-zero (naming the
offending service/URL) on failure. Neither installs anything — they are
one-off checks a human runs manually, any time (after a redeploy, after a
reboot, before a demo).

---

## 11. Ongoing operations

- **Redeploy after a code change:** `git pull && docker compose up --build -d`.
- **Logs:** `docker compose logs -f [service]` — this is the full extent of
  monitoring in scope for this project (no observability dashboard).
- **Backup:** periodically run `pg_dump` manually (e.g. before a work
  session) and copy the dump off the VM. This is a human habit, not a
  cron job — do not script it as a scheduled task.
- **Reboots:** the VM reboots cleanly — Docker's own restart policy brings
  all 3 containers back up; `/etc/fstab`'s swap entry (Plan B) re-activates
  swap automatically on boot (this is OS-level persistence, not a
  keep-warm/cron mechanism — nothing pings the app on a schedule).
