#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

prepare_stack_ensure_dir_from_env KOMETA_CONFIG_PATH "${HOME}/.config/kometa"
prepare_stack_ensure_dir_from_env KOMETA_DATA_PATH "${HOME}/.config/kometa/data"

_cfg="$(prepare_stack__expand_home_in_path "${HOME}/.config/kometa")"
if [[ -f stack.env ]]; then
  _line=$(grep -E "^KOMETA_CONFIG_PATH=" stack.env 2>/dev/null | tail -1) || true
  if [[ -n "$_line" ]]; then
    _val="${_line#*=}"; _val="${_val%$'\r$'}"
    _val="${_val#\"}"; _val="${_val%\"}"; _val="${_val#'}"; _val="${_val%'}"
    [[ -n "$_val" ]] && _cfg="$(prepare_stack__expand_home_in_path "$_val")"
  fi
fi
mkdir -p "$_cfg"
if [[ ! -f "$_cfg/config.yml" ]]; then
  cp "$_PREPDIR/config.yml.example" "$_cfg/config.yml"
  prepare_stack_msg "created ${_cfg}/config.yml from config.yml.example — configure Plex URL and token."
else
  prepare_stack_msg "${_cfg}/config.yml already exists (left unchanged)."
fi

prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "monitor"
prepare_stack_end
