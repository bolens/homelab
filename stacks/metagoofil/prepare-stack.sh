#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

prepare_stack_ensure_dir_from_env METAGOOFIL_DATA_PATH "${HOME}/.config/metagoofil/data"

prepare_stack_copy_caddy
prepare_stack_end
