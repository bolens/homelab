#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

_cfg="$(prepare_stack__expand_home_in_path "${HOME}/.config/grafana/provisioning/datasources/datasources.yml")"
if [[ -f stack.env ]]; then
  _line=$(grep -E "^GRAFANA_DATASOURCES_PATH=" stack.env 2>/dev/null | tail -1) || true
  if [[ -n "$_line" ]]; then
    _val="${_line#*=}"; _val="${_val%$'\r$'}"
    _val="${_val#\"}"; _val="${_val%\"}"; _val="${_val#'}"; _val="${_val%'}"
    [[ -n "$_val" ]] && _cfg="$(prepare_stack__expand_home_in_path "$_val")"
  fi
fi
mkdir -p "$(dirname "$_cfg")"
if [[ ! -f "$_cfg" ]]; then
  cp "$_PREPDIR/datasources.yml.example" "$_cfg"
  prepare_stack_msg "created ${_cfg} from datasources.yml.example — edit datasource URLs."
else
  prepare_stack_msg "${_cfg} already exists (left unchanged)."
fi

_cfg="$(prepare_stack__expand_home_in_path "${HOME}/.config/grafana/provisioning/dashboards")"
if [[ -f stack.env ]]; then
  _line=$(grep -E "^GRAFANA_PROVISIONING_DIR=" stack.env 2>/dev/null | tail -1) || true
  if [[ -n "$_line" ]]; then
    _val="${_line#*=}"; _val="${_val%$'\r$'}"
    _val="${_val#\"}"; _val="${_val%\"}"; _val="${_val#'}"; _val="${_val%'}"
    [[ -n "$_val" ]] && _cfg="$(prepare_stack__expand_home_in_path "$_val")"
  fi
fi
mkdir -p "$_cfg"
if [[ ! -f "$_cfg/dashboards.yml" ]]; then
  cp "$_PREPDIR/provisioning_dashboards.example" "$_cfg/dashboards.yml"
  prepare_stack_msg "created ${_cfg}/dashboards.yml from provisioning_dashboards.example — place .json dashboard files in this dir."
else
  prepare_stack_msg "${_cfg}/dashboards.yml already exists (left unchanged)."
fi

prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "telemetry" "true"
prepare_stack_ensure_docker_network "ingress-admin"
prepare_stack_end
