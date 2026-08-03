#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_dir_from_env "HANDBRAKE_CONFIG_PATH" "${HOME}/.config/handbrake"
prepare_stack_msg "verify HANDBRAKE_STORAGE_PATH, HANDBRAKE_WATCH_PATH, and HANDBRAKE_OUTPUT_PATH exist on mounted storage; they are intentionally not created here."
prepare_stack_ensure_docker_network "monitor"
prepare_stack_end
