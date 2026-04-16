#!/usr/bin/env bash
# Apply reconcile threshold compose overlay by environment.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: scripts/apply-reconcile-profile.sh <dev|staging|prod> [--no-verify]

Examples:
  scripts/apply-reconcile-profile.sh staging
  scripts/apply-reconcile-profile.sh prod --no-verify

Default behavior:
  - Runs docker compose with docker-compose.reconcile-<env>.yml overlay
  - Verifies effective READ_MODEL_RECONCILE_ALERT_* env in asking-api
  - Runs reconcile smoke check with stack.env.dev loaded (unless --no-verify)
EOF
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage >&2
  exit 1
fi

PROFILE="$1"
VERIFY=true
if [[ $# -eq 2 ]]; then
  if [[ "$2" == "--no-verify" ]]; then
    VERIFY=false
  else
    usage >&2
    exit 1
  fi
fi

case "${PROFILE}" in
  dev|staging|prod) ;;
  *)
    echo "Invalid profile: ${PROFILE}" >&2
    usage >&2
    exit 1
    ;;
esac

OVERLAY_FILE="${STACK_DIR}/docker-compose.reconcile-${PROFILE}.yml"
if [[ ! -f "${OVERLAY_FILE}" ]]; then
  echo "Missing overlay file: ${OVERLAY_FILE}" >&2
  exit 1
fi

echo "[reconcile-profile] applying profile=${PROFILE}"
docker compose \
  -f "${STACK_DIR}/docker-compose.yml" \
  -f "${OVERLAY_FILE}" \
  up -d --build

echo "[reconcile-profile] effective reconcile env:"
docker compose exec -T asking-api env | grep READ_MODEL_RECONCILE_ALERT_

if [[ "${VERIFY}" == "true" ]]; then
  echo "[reconcile-profile] running reconcile smoke check"
  bash "${STACK_DIR}/scripts/with-dev-env.sh" \
    pnpm --dir "${STACK_DIR}" --filter api run read-model:reconcile-smoke
else
  echo "[reconcile-profile] skipped smoke verify (--no-verify)"
fi

echo "[reconcile-profile] done"
