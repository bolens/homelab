#!/usr/bin/env bash
# Prepare local files before first deploy. Safe to re-run: existing stack.env and caddy_snippet.conf are not overwritten.
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

prepare_stack_ensure_dir_from_env BESZEL_DATA_DIR "${HOME:-/tmp}/.local/share/beszel"

prepare_stack_copy_caddy

if [[ -f stack.env ]] && [[ ! -e .env ]]; then
  ln -s stack.env .env
  prepare_stack_msg "created .env → stack.env (docker compose reads .env for bind-mount path interpolation)"
fi

prepare_stack_end
