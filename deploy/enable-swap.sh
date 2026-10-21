#!/usr/bin/env bash
# enable-swap.sh — idempotent swap setup for Plan B (VM.Standard.E2.1.Micro,
# 1 OCPU / 1GB RAM). Run once over SSH on the VM before `docker compose up`.
#
# Not needed on Plan A (Ampere A1, 12GB RAM) — only Plan B's tight memory
# budget requires swap to avoid OOM kills under the Postgres + Uvicorn +
# in-memory ML artifact footprint.
#
# This is a one-time, manually-invoked setup action — it installs no
# cron job, systemd timer, or scheduled task (RNF-06, AD-9). Re-running it
# (e.g. after a reboot during testing, or an operator re-running the
# runbook) is safe: it detects existing swap and makes no duplicate changes.

set -euo pipefail

SWAPFILE="/swapfile"
SWAPSIZE="2G"

echo "== enable-swap.sh: Plan B swap setup =="

# --- Idempotency check 1: is swap already active? ---
if swapon --show | grep -q "${SWAPFILE}"; then
  echo "[skip] Swap already active on ${SWAPFILE} (swapon --show):"
  swapon --show
  exit 0
fi

# --- Idempotency check 2: does the swapfile already exist but isn't on? ---
if [ -f "${SWAPFILE}" ]; then
  echo "[info] ${SWAPFILE} already exists but is not active — activating it."
  sudo chmod 600 "${SWAPFILE}"
  sudo swapon "${SWAPFILE}"
else
  echo "[info] Creating ${SWAPSIZE} swapfile at ${SWAPFILE}..."
  if command -v fallocate >/dev/null 2>&1; then
    sudo fallocate -l "${SWAPSIZE}" "${SWAPFILE}"
  else
    # fallback for filesystems without fallocate support
    # Derive dd's count (in MB, matching bs=1M) from SWAPSIZE instead of
    # hardcoding it, so changing SWAPSIZE above stays in sync.
    SIZE_NUM="${SWAPSIZE%[GgMm]}"
    SIZE_UNIT="${SWAPSIZE: -1}"
    case "${SIZE_UNIT}" in
      G|g) DD_COUNT_MB=$((SIZE_NUM * 1024)) ;;
      M|m) DD_COUNT_MB=${SIZE_NUM} ;;
      *) echo "[error] Unrecognized SWAPSIZE unit in '${SWAPSIZE}' (expected G or M suffix)." >&2; exit 1 ;;
    esac
    sudo dd if=/dev/zero of="${SWAPFILE}" bs=1M count="${DD_COUNT_MB}" status=progress
  fi
  sudo chmod 600 "${SWAPFILE}"
  sudo mkswap "${SWAPFILE}"
  sudo swapon "${SWAPFILE}"
fi

# --- Idempotency check 3: persist via /etc/fstab, skip if entry exists ---
FSTAB_ENTRY="${SWAPFILE} none swap sw 0 0"
if grep -qs "^${SWAPFILE} " /etc/fstab; then
  echo "[skip] /etc/fstab already has an entry for ${SWAPFILE}."
else
  echo "[info] Adding ${SWAPFILE} to /etc/fstab for persistence across reboots."
  echo "${FSTAB_ENTRY}" | sudo tee -a /etc/fstab >/dev/null
fi

echo "== Swap enabled =="
swapon --show
