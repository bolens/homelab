#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

prepare_stack_ensure_dir_from_env YOURLS_CONFIG_DIR "${HOME}/.config/yourls"

_cfg="$(prepare_stack__expand_home_in_path "${HOME}/.config/yourls")"
if [[ -f stack.env ]]; then
  _line=$(grep -E "^YOURLS_CONFIG_DIR=" stack.env 2>/dev/null | tail -1) || true
  if [[ -n "$_line" ]]; then
    _val="${_line#*=}"; _val="${_val%$'\r$'}"
    _val="${_val#\"}"; _val="${_val%\"}"; _val="${_val#'}"; _val="${_val%'}"
    [[ -n "$_val" ]] && _cfg="$(prepare_stack__expand_home_in_path "$_val")"
  fi
fi
mkdir -p "$_cfg"
if [[ ! -f "$_cfg/vhost.conf" ]]; then
  cp "$_PREPDIR/vhost.conf.example" "$_cfg/vhost.conf"
  prepare_stack_msg "created ${_cfg}/vhost.conf from vhost.conf.example."
else
  prepare_stack_msg "${_cfg}/vhost.conf already exists (left unchanged)."
fi
mkdir -p "$_cfg"
if [[ ! -f "$_cfg/proxy-https-fix.php" ]]; then
  cp "$_PREPDIR/proxy-https-fix.php.example" "$_cfg/proxy-https-fix.php"
  prepare_stack_msg "created ${_cfg}/proxy-https-fix.php from proxy-https-fix.php.example."
else
  prepare_stack_msg "${_cfg}/proxy-https-fix.php already exists (left unchanged)."
fi

prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "ingress-public"
prepare_stack_end
