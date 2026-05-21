#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_msg "POSTGRES_PASSWORD must be set in stack.env before first deploy (generate: openssl rand -hex 32)."

prepare_stack_ensure_dir_from_env GUACAMOLE_CONFIG_PATH "${HOME}/.config/guacamole"

_cfg="$(prepare_stack__expand_home_in_path "${HOME}/.config/guacamole")"
if [[ -f stack.env ]]; then
  _line=$(grep -E "^GUACAMOLE_CONFIG_PATH=" stack.env 2>/dev/null | tail -1) || true
  if [[ -n "$_line" ]]; then
    _val="${_line#*=}"; _val="${_val%$'\r$'}"
    _val="${_val#\"}"; _val="${_val%\"}"; _val="${_val#'}"; _val="${_val%'}"
    [[ -n "$_val" ]] && _cfg="$(prepare_stack__expand_home_in_path "$_val")"
  fi
fi
mkdir -p "$_cfg"
if [[ ! -f "$_cfg/guacamole.properties" ]]; then
  cp "$_PREPDIR/guacamole.properties.example" "$_cfg/guacamole.properties"
  prepare_stack_msg "created ${_cfg}/guacamole.properties from guacamole.properties.example — GUACAMOLE-2127 workaround."
else
  prepare_stack_msg "${_cfg}/guacamole.properties already exists (left unchanged)."
fi

prepare_stack_copy_caddy
prepare_stack_end
