#!/usr/bin/env bash
# prewarm.sh — Plan C (Story 6.3) manual pre-warm / health-check.
#
# Usage:
#   deploy/prewarm.sh <backend-base-url>
#   deploy/prewarm.sh https://sinaliza-backend.onrender.com
#
# Hits the backend's unauthenticated /openapi.json route once to force a
# cold-start wake-up on Render (and transitively on Neon, via the first
# real query the request triggers) before a live demonstration.
#
# THIS IS A ONE-OFF HUMAN ACTION. Run it by hand, a few minutes before a
# demo. Do NOT wire this into a cron job, systemd timer, CI schedule, or
# any other recurring trigger — a scheduled pre-warm is a keep-warm ping,
# which would violate RNF-06/AD-9's no-cron constraint exactly like the
# thing Plan C's architecture is designed to avoid everywhere else in this
# system. If you find yourself tempted to automate this script's
# invocation on a timer, don't — that defeats the reason it exists as a
# manual script instead of a background service.
#
# Unlike deploy/smoke-test.sh (Story 6.2), this script has NO latency
# threshold and does not fail on slowness: a slow first response here is
# the expected, documented Plan C cold start (see
# deploy/plan-c-contingency-runbook.md's RNF-01 waiver), not a defect.
# It only fails on an outright connection error, meaning the service
# never woke up at all.

set -uo pipefail

BASE_URL="${1:-}"
if [ -z "${BASE_URL}" ]; then
  echo "Usage: $0 <backend-base-url>" >&2
  echo "Example: $0 https://sinaliza-backend.onrender.com" >&2
  exit 2
fi

# Strip trailing slash for clean concatenation.
BASE_URL="${BASE_URL%/}"

# No /api prefix: this script talks to the Render backend directly, not
# through the Vercel rewrite (deploy/vercel.json) that only exists for the
# browser-facing frontend. See plan-c-contingency-runbook.md Section 5.
URL="${BASE_URL}/openapi.json"

# Generous timeout: a cold start is exactly what this script expects to
# wait through, so it must not give up at a 5-second RNF-01-style budget.
MAX_WAIT_SECONDS=60

echo "== prewarm.sh: Plan C manual pre-warm =="
echo "Target: ${URL}"
echo "(waiting up to ${MAX_WAIT_SECONDS}s for a cold start to resolve)"
echo

RESPONSE="$(curl --max-time "${MAX_WAIT_SECONDS}" -s -o /dev/null \
  -w 'HTTP_CODE:%{http_code} TIME:%{time_total}' \
  "${URL}" 2>&1)"
CURL_EXIT=$?

if [ "${CURL_EXIT}" -ne 0 ]; then
  echo "[FAIL] Could not reach ${URL} (curl exit ${CURL_EXIT})."
  echo "       The service may still be deploying, asleep beyond this"
  echo "       timeout, or down. Do not start the demo yet — retry this"
  echo "       script, or check the Render dashboard."
  exit 1
fi

HTTP_CODE="$(echo "${RESPONSE}" | grep -o 'HTTP_CODE:[0-9]*' | cut -d: -f2)"
TIME_TOTAL="$(echo "${RESPONSE}" | grep -o 'TIME:[0-9.]*' | cut -d: -f2)"

if ! [[ "${HTTP_CODE}" =~ ^[23][0-9][0-9]$ ]]; then
  echo "[FAIL] ${URL} responded with HTTP ${HTTP_CODE:-unknown} (expected 2xx/3xx)."
  echo "       Do not start the demo yet — check DATABASE_URL/JWT_SECRET on"
  echo "       Render and the service's deploy logs."
  exit 1
fi

echo "[OK] ${URL} responded ${HTTP_CODE} in ${TIME_TOTAL}s."
if awk -v t="${TIME_TOTAL}" 'BEGIN { exit !(t > 5) }'; then
  echo "     (took longer than 5s — this was the expected cold start;"
  echo "      the service should now be warm for the demo that follows)"
fi
echo
echo "== Pre-warm complete. Safe to start the demo. =="
exit 0
