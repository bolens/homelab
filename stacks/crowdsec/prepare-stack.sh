#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

prepare_stack_ensure_dir_from_env CROWDSEC_CONFIG_DIR "${HOME}/.config/crowdsec"

_cfg="$(prepare_stack__expand_home_in_path "${HOME}/.config/crowdsec")"
if [[ -f stack.env ]]; then
  _line=$(grep -E "^CROWDSEC_CONFIG_DIR=" stack.env 2>/dev/null | tail -1) || true
  if [[ -n "$_line" ]]; then
    _val="${_line#*=}"; _val="${_val%$'\r$'}"
    _val="${_val#\"}"; _val="${_val%\"}"; _val="${_val#'}"; _val="${_val%'}"
    [[ -n "$_val" ]] && _cfg="$(prepare_stack__expand_home_in_path "$_val")"
  fi
fi
mkdir -p "$_cfg"
if [[ ! -f "$_cfg/acquis.yaml" ]]; then
  cp "$_PREPDIR/acquis.yaml.example" "$_cfg/acquis.yaml"
  prepare_stack_msg "created ${_cfg}/acquis.yaml from acquis.yaml.example — review log source paths."
else
  prepare_stack_msg "${_cfg}/acquis.yaml already exists (left unchanged)."
fi

prepare_stack_copy_caddy
prepare_stack_end
