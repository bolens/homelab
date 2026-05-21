#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

prepare_stack_ensure_dir_from_env ASF_CONFIG_DIR "${HOME}/.config/archisteamfarm"

_cfg="$(prepare_stack__expand_home_in_path "${HOME}/.config/archisteamfarm")"
if [[ -f stack.env ]]; then
  _line=$(grep -E "^ASF_CONFIG_DIR=" stack.env 2>/dev/null | tail -1) || true
  if [[ -n "$_line" ]]; then
    _val="${_line#*=}"; _val="${_val%$'\r$'}"
    _val="${_val#\"}"; _val="${_val%\"}"; _val="${_val#'}"; _val="${_val%'}"
    [[ -n "$_val" ]] && _cfg="$(prepare_stack__expand_home_in_path "$_val")"
  fi
fi
mkdir -p "$_cfg"
if [[ ! -f "$_cfg/ASF.json" ]]; then
  cp "$_PREPDIR/ASF.json.example" "$_cfg/ASF.json"
  prepare_stack_msg "created ${_cfg}/ASF.json from ASF.json.example — configure SteamOwnerID and other settings."
else
  prepare_stack_msg "${_cfg}/ASF.json already exists (left unchanged)."
fi

prepare_stack_ensure_docker_network "monitor"
prepare_stack_end
