#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

prepare_stack_ensure_dir_from_env RECONFTW_CONFIG_DIR "${HOME}/.config/reconftw"

_cfg="$(prepare_stack__expand_home_in_path "${HOME}/.config/reconftw")"
if [[ -f stack.env ]]; then
  _line=$(grep -E "^RECONFTW_CONFIG_DIR=" stack.env 2>/dev/null | tail -1) || true
  if [[ -n "$_line" ]]; then
    _val="${_line#*=}"; _val="${_val%$'\r$'}"
    _val="${_val#\"}"; _val="${_val%\"}"; _val="${_val#'}"; _val="${_val%'}"
    [[ -n "$_val" ]] && _cfg="$(prepare_stack__expand_home_in_path "$_val")"
  fi
fi
mkdir -p "$_cfg/Recon"
if [[ ! -f "$_cfg/reconftw.cfg" ]]; then
  if command -v curl >/dev/null 2>&1; then
    prepare_stack_msg "downloading reconftw.cfg from upstream..."
    curl -sSL -o "$_cfg/reconftw.cfg" https://raw.githubusercontent.com/six2dez/reconftw/main/reconftw.cfg
    prepare_stack_msg "created ${_cfg}/reconftw.cfg — review API keys and settings."
  else
    prepare_stack_msg "curl not in PATH — place reconftw.cfg manually at ${_cfg}/reconftw.cfg."
  fi
else
  prepare_stack_msg "${_cfg}/reconftw.cfg already exists (left unchanged)."
fi

prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "security-research"
prepare_stack_end
