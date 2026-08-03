#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_dir_from_env "RACKULA_SOURCE_PATH" "${HOME}/dev/rackula-source"
prepare_stack_ensure_dir_from_env "RACKULA_OUTPUT_PATH" "${HOME}/dev/rackula-output"
prepare_stack_end
