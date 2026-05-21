#!/usr/bin/env bash
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_ensure_dir_from_env "DOZZLE_CONFIG_DIR" "${HOME}/.config/dozzle"
prepare_stack_ensure_docker_network "monitor"

_doz_dir="${HOME}/.config/dozzle"
if [[ -f "$_PREPDIR/stack.env" ]]; then
	_line="$(grep -E '^DOZZLE_CONFIG_DIR=' "$_PREPDIR/stack.env" 2>/dev/null | tail -1 || true)"
	if [[ -n "$_line" ]]; then
		_val="${_line#*=}"
		_val="${_val%$'\r'}"
		_val="${_val#\"}"
		_val="${_val%\"}"
		_val="${_val#\'}"
		_val="${_val%\'}"
		[[ -n "$_val" ]] && _doz_dir="$_val"
	fi
fi
_doz_dir="${_doz_dir//\$\{HOME\}/${HOME:-}}"
if [[ "${_doz_dir:0:1}" == '~' ]]; then
	_doz_dir="${HOME:-}${_doz_dir:1}"
fi
mkdir -p "$_doz_dir"

if [[ ! -f "$_doz_dir/users.yaml" && ! -f "$_doz_dir/users.yml" ]]; then
	cp "$_PREPDIR/users.yaml.example" "$_doz_dir/users.yaml"
	prepare_stack_msg "created $_doz_dir/users.yaml from users.yaml.example — replace password (dozzle generate …) before enabling DOZZLE_AUTH_PROVIDER=simple."
else
	prepare_stack_msg "users.yaml or users.yml already present under $_doz_dir (left unchanged)."
fi

prepare_stack_end
