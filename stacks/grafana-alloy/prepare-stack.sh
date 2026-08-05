#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

_cfg="$(prepare_stack__expand_home_in_path "${HOME}/.config/grafana-alloy/config.alloy")"
if [[ -f stack.env ]]; then
  _line=$(grep -E "^ALLOY_CONFIG_PATH=" stack.env 2>/dev/null | tail -1) || true
  if [[ -n "$_line" ]]; then
    _val="${_line#*=}"; _val="${_val%$'\r$'}"
    _val="${_val#\"}"; _val="${_val%\"}"; _val="${_val#'}"; _val="${_val%'}"
    [[ -n "$_val" ]] && _cfg="$(prepare_stack__expand_home_in_path "$_val")"
  fi
fi
mkdir -p "$(dirname "$_cfg")"
if [[ ! -f "$_cfg" ]]; then
  cp "$_PREPDIR/config.alloy.example" "$_cfg"
  prepare_stack_msg "created ${_cfg} from config.alloy.example — configure your pipelines before starting."
else
  prepare_stack_msg "${_cfg} already exists (left unchanged)."
fi

prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "telemetry" "true"
prepare_stack_end
