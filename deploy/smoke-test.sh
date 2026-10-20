#!/usr/bin/env bash
# smoke-test.sh — RNF-01 verification: checks that the deployed system
# responds within 5 seconds under normal conditions.
#
# Usage:
#   deploy/smoke-test.sh <base-url>
#   deploy/smoke-test.sh http://localhost
#   deploy/smoke-test.sh http://<vm-public-ip>
#
# Checks the frontend root and a representative /api/* route. Prints
# per-request latency and a pass/fail summary. Exits non-zero (naming the
# offending URL) if any request exceeds 5s or returns a connection error /
# non-2xx/3xx status.
#
# Manually invoked — not scheduled, not a keep-warm ping (RNF-06, AD-9).

set -uo pipefail

BASE_URL="${1:-}"
if [ -z "${BASE_URL}" ]; then
  echo "Usage: $0 <base-url>" >&2
  echo "Example: $0 http://localhost" >&2
  exit 2
fi

# Strip trailing slash for clean concatenation.
BASE_URL="${BASE_URL%/}"

THRESHOLD_SECONDS=5

# Representative endpoints: frontend root (served by Nginx) and a
# representative /api/* route. /api/openapi.json is used for the latter —
# FastAPI serves it unauthenticated by default (no `dependencies` on it,
# unlike every domain router in this app, which all require a JWT — see
# backend/app/presentation/*/router.py), so it proves the full reverse-proxy
# (Nginx /api/ -> backend:8000/) + backend round-trip is within budget with
# a real 200 response, without needing valid demo credentials baked into
# this script.
CHECKS=(
  "GET|${BASE_URL}/|frontend root"
  "GET|${BASE_URL}/api/openapi.json|API route (OpenAPI schema)"
)

FAILED=0
FAILED_URLS=()

echo "== smoke-test.sh: RNF-01 5-second response check =="
echo "Base URL: ${BASE_URL}"
echo "Threshold: ${THRESHOLD_SECONDS}s"
echo

for check in "${CHECKS[@]}"; do
  IFS='|' read -r METHOD URL LABEL <<< "${check}"

  echo "-- ${LABEL}: ${METHOD} ${URL} --"

  RESPONSE="$(curl --max-time $((THRESHOLD_SECONDS * 2)) -s -o /dev/null \
    -w 'HTTP_CODE:%{http_code} TIME:%{time_total}' \
    -X "${METHOD}" \
    "${URL}" 2>&1)"
  CURL_EXIT=$?

  if [ "${CURL_EXIT}" -ne 0 ]; then
    echo "[fail] ${LABEL} (${URL}): curl error (exit ${CURL_EXIT}) — connection failed or timed out"
    FAILED=1
    FAILED_URLS+=("${URL} (connection error)")
    continue
  fi

  HTTP_CODE="$(echo "${RESPONSE}" | grep -o 'HTTP_CODE:[0-9]*' | cut -d: -f2)"
  TIME_TOTAL="$(echo "${RESPONSE}" | grep -o 'TIME:[0-9.]*' | cut -d: -f2)"

  echo "  status=${HTTP_CODE} time=${TIME_TOTAL}s"

  # TIME_TOTAL must look like a number before it's fed to awk — an empty or
  # non-numeric value would otherwise be treated as 0 by awk and falsely pass.
  if ! [[ "${TIME_TOTAL}" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
    echo "[fail] ${LABEL} (${URL}): could not parse response time ('${TIME_TOTAL}') from curl output"
    FAILED=1
    FAILED_URLS+=("${URL} (unparseable time)")
    continue
  fi

  # Status must be 2xx or 3xx.
  if ! [[ "${HTTP_CODE}" =~ ^[23][0-9][0-9]$ ]]; then
    echo "[fail] ${LABEL} (${URL}): non-2xx/3xx status ${HTTP_CODE}"
    FAILED=1
    FAILED_URLS+=("${URL} (status=${HTTP_CODE})")
    continue
  fi

  # Latency must be under threshold. Compare using awk (no bc dependency).
  OVER_THRESHOLD="$(awk -v t="${TIME_TOTAL}" -v th="${THRESHOLD_SECONDS}" 'BEGIN { print (t > th) ? 1 : 0 }')"
  if [ "${OVER_THRESHOLD}" -eq 1 ]; then
    echo "[fail] ${LABEL} (${URL}): ${TIME_TOTAL}s exceeds ${THRESHOLD_SECONDS}s threshold"
    FAILED=1
    FAILED_URLS+=("${URL} (time=${TIME_TOTAL}s)")
    continue
  fi

  echo "[pass] ${LABEL}: ${TIME_TOTAL}s (status ${HTTP_CODE})"
done

echo
if [ "${FAILED}" -eq 0 ]; then
  echo "== PASS: all checked endpoints responded within ${THRESHOLD_SECONDS}s =="
  exit 0
else
  echo "== FAIL: issues found with: ${FAILED_URLS[*]} =="
  exit 1
fi
