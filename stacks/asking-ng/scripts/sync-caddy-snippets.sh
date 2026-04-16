#!/usr/bin/env bash
# Render caddy snippets from caddy_snippet.conf.template.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_FILE="${STACK_DIR}/caddy_snippet.conf.template"
EXAMPLE_FILE="${STACK_DIR}/caddy_snippet.conf.example"
LOCAL_FILE="${STACK_DIR}/caddy_snippet.conf"

if [[ ! -f "${TEMPLATE_FILE}" ]]; then
  echo "[sync-caddy] missing template: ${TEMPLATE_FILE}" >&2
  exit 1
fi

render_template() {
  local hostname="${1:?hostname}"
  local target="${2:?target file}"
  sed "s/{{PUBLIC_HOSTNAME}}/${hostname}/g" "${TEMPLATE_FILE}" > "${target}"
}

render_template "asking-ng.example.com" "${EXAMPLE_FILE}"
echo "[sync-caddy] wrote ${EXAMPLE_FILE} from template."

if [[ -n "${ASKING_NG_PUBLIC_HOSTNAME:-}" ]]; then
  render_template "${ASKING_NG_PUBLIC_HOSTNAME}" "${LOCAL_FILE}"
  echo "[sync-caddy] wrote ${LOCAL_FILE} from template (ASKING_NG_PUBLIC_HOSTNAME)."
elif [[ ! -f "${LOCAL_FILE}" ]]; then
  cp "${EXAMPLE_FILE}" "${LOCAL_FILE}"
  echo "[sync-caddy] created ${LOCAL_FILE} from example (set ASKING_NG_PUBLIC_HOSTNAME to prefill)."
else
  echo "[sync-caddy] kept existing ${LOCAL_FILE} unchanged."
fi
