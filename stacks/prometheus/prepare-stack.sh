#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

_cfg="$(prepare_stack__expand_home_in_path "${HOME}/.config/prometheus/prometheus.yml")"
if [[ -f stack.env ]]; then
  _line=$(grep -E "^PROMETHEUS_CONFIG_PATH=" stack.env 2>/dev/null | tail -1) || true
  if [[ -n "$_line" ]]; then
    _val="${_line#*=}"; _val="${_val%$'\r$'}"
    _val="${_val#\"}"; _val="${_val%\"}"; _val="${_val#'}"; _val="${_val%'}"
    [[ -n "$_val" ]] && _cfg="$(prepare_stack__expand_home_in_path "$_val")"
  fi
fi
mkdir -p "$(dirname "$_cfg")"
if [[ ! -f "$_cfg" ]]; then
  cp "$_PREPDIR/prometheus.yml.example" "$_cfg"
  prepare_stack_msg "created ${_cfg} from prometheus.yml.example — review scrape configs."
else
  prepare_stack_msg "${_cfg} already exists (left unchanged)."
fi

_cfg="$(prepare_stack__expand_home_in_path "${HOME}/.config/prometheus/rules")"
if [[ -f stack.env ]]; then
  _line=$(grep -E "^PROMETHEUS_RULES_DIR=" stack.env 2>/dev/null | tail -1) || true
  if [[ -n "$_line" ]]; then
    _val="${_line#*=}"; _val="${_val%$'\r$'}"
    _val="${_val#\"}"; _val="${_val%\"}"; _val="${_val#'}"; _val="${_val%'}"
    [[ -n "$_val" ]] && _cfg="$(prepare_stack__expand_home_in_path "$_val")"
  fi
fi
mkdir -p "$_cfg"
if [[ ! -f "$_cfg/alerts.yml" ]]; then
  cp "$_PREPDIR/alerts.yml.example" "$_cfg/alerts.yml"
  prepare_stack_msg "created ${_cfg}/alerts.yml from alerts.yml.example."
else
  prepare_stack_msg "${_cfg}/alerts.yml already exists (left unchanged)."
fi

if [[ ! -f "$_PREPDIR/watchtower_bearer_token" ]] && [[ -f "$_PREPDIR/watchtower_bearer_token.example" ]]; then
  cp "$_PREPDIR/watchtower_bearer_token.example" "$_PREPDIR/watchtower_bearer_token"
  prepare_stack_msg "created watchtower_bearer_token from example — set token to match Watchtower config."
else
  prepare_stack_msg "watchtower_bearer_token already exists (left unchanged)."
fi

prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "monitor"
prepare_stack_ensure_docker_network "observability"
prepare_stack_end
