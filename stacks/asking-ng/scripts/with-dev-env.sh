#!/usr/bin/env bash
# Run a command with stack.env.dev loaded (if present).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEV_ENV_FILE="${STACK_DIR}/stack.env.dev"

if [[ $# -eq 0 ]]; then
  echo "usage: $0 <command> [args...]" >&2
  exit 1
fi

if [[ -f "${DEV_ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${DEV_ENV_FILE}"
  set +a
fi

is_smoke_command=false
for arg in "$@"; do
  case "$arg" in
    *slo-smoke*|*read-model:reconcile-smoke*)
      is_smoke_command=true
      break
      ;;
  esac
done

if [[ "${is_smoke_command}" == "true" ]]; then
  base_url="${SLO_SMOKE_BASE_URL:-${RECONCILE_SMOKE_BASE_URL:-http://127.0.0.1:3001}}"
  if ! curl -fsS --max-time 2 "${base_url%/}/ready" >/dev/null 2>&1; then
    echo "[with-dev-env] API not reachable at ${base_url%/}/ready" >&2
    echo "[with-dev-env] Start stack/API first, or adjust SLO_SMOKE_BASE_URL / RECONCILE_SMOKE_BASE_URL in stack.env.dev." >&2
    exit 1
  fi
fi

exec "$@"
