#!/usr/bin/env bash
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "ingress-public"
prepare_stack_ensure_docker_network "ai-backend" "true"

_settings_path="${SEARXNG_SETTINGS_PATH:-${HOME}/.config/searx-ng/settings.yml}"
if [[ -f "$_PREPDIR/stack.env" ]]; then
  _line="$(grep -E '^SEARXNG_SETTINGS_PATH=' "$_PREPDIR/stack.env" 2>/dev/null | tail -1 || true)"
  if [[ -n "$_line" ]]; then
    _settings_path="${_line#*=}"
    _settings_path="${_settings_path#\"}"
    _settings_path="${_settings_path%\"}"
    _settings_path="${_settings_path#\'}"
    _settings_path="${_settings_path%\'}"
  fi
fi

_settings_path="${_settings_path//\$\{HOME\}/${HOME:-}}"
if [[ "${_settings_path:0:1}" == "~" ]]; then
  _settings_path="${HOME:-}${_settings_path:1}"
fi

mkdir -p "$(dirname "$_settings_path")"
if [[ ! -f "$_settings_path" ]]; then
  cp "$_PREPDIR/settings.yml.example" "$_settings_path"
  prepare_stack_msg "created settings file at $_settings_path from settings.yml.example."
else
  prepare_stack_msg "settings file already exists at $_settings_path (left unchanged)."
fi

prepare_stack_end
