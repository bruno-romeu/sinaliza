#!/usr/bin/env bash
# verify-always-on.sh — confirms the always-on / no-scale-to-zero AC (RNF-04)
# holds for the running stack: all 3 services (postgres, backend, frontend)
# are Up/running and carry `restart: unless-stopped`.
#
# Usage:
#   deploy/verify-always-on.sh              # run locally on the VM
#   deploy/verify-always-on.sh user@host    # run checks over SSH
#
# This is a manually-invoked verification script, not a monitoring daemon —
# it runs once per invocation and exits. No cron/systemd timer is installed
# or implied (RNF-06, AD-9).

set -euo pipefail

SSH_HOST="${1:-}"
EXPECTED_SERVICES=("postgres" "backend" "frontend")
EXPECTED_RESTART_POLICY="unless-stopped"

run() {
  if [ -n "${SSH_HOST}" ]; then
    ssh -o ConnectTimeout=10 -o BatchMode=yes "${SSH_HOST}" "cd ~/sinaliza && $1"
  else
    bash -c "$1"
  fi
}

echo "== verify-always-on.sh =="
if [ -n "${SSH_HOST}" ]; then
  echo "Target: ${SSH_HOST} (over SSH)"
else
  echo "Target: local host"
fi

FAILED=0
FAILED_SERVICES=()

# --- Check 1: docker compose ps reports all services running ---
echo
echo "-- docker compose ps --"
PS_OUTPUT="$(run 'docker compose ps --format "{{.Service}} {{.State}}"' || true)"
echo "${PS_OUTPUT}"

if [ -z "${PS_OUTPUT}" ]; then
  echo "[fail] Could not read 'docker compose ps' output — is the stack running from the compose project directory?"
  exit 1
fi

for svc in "${EXPECTED_SERVICES[@]}"; do
  LINE="$(echo "${PS_OUTPUT}" | grep "^${svc} " || true)"
  if [ -z "${LINE}" ]; then
    echo "[fail] Service '${svc}' not found in 'docker compose ps' output."
    FAILED=1
    FAILED_SERVICES+=("${svc} (not found)")
    continue
  fi
  STATE="$(echo "${LINE}" | awk '{print $2}')"
  case "${STATE}" in
    running|Up|Up*)
      echo "[pass] ${svc}: ${STATE}"
      ;;
    *)
      echo "[fail] ${svc}: expected Up/running, got '${STATE}'"
      FAILED=1
      FAILED_SERVICES+=("${svc} (state=${STATE})")
      ;;
  esac
done

# --- Check 2: restart policy is unless-stopped on each service's container ---
echo
echo "-- docker inspect: RestartPolicy --"
for svc in "${EXPECTED_SERVICES[@]}"; do
  CONTAINER_ID="$(run "docker compose ps -q ${svc}" || true)"
  if [ -z "${CONTAINER_ID}" ]; then
    echo "[fail] ${svc}: no container id found (service not running?)"
    FAILED=1
    FAILED_SERVICES+=("${svc} (no container)")
    continue
  fi
  POLICY="$(run "docker inspect --format '{{.HostConfig.RestartPolicy.Name}}' ${CONTAINER_ID}" || true)"
  if [ "${POLICY}" = "${EXPECTED_RESTART_POLICY}" ]; then
    echo "[pass] ${svc}: restart policy = ${POLICY}"
  else
    echo "[fail] ${svc}: expected restart policy '${EXPECTED_RESTART_POLICY}', got '${POLICY}'"
    FAILED=1
    FAILED_SERVICES+=("${svc} (restart_policy=${POLICY})")
  fi
done

echo
if [ "${FAILED}" -eq 0 ]; then
  echo "== PASS: all 3 services Up/running with restart: unless-stopped =="
  exit 0
else
  echo "== FAIL: issues found with: ${FAILED_SERVICES[*]} =="
  exit 1
fi
