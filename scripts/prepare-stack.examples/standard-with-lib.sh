#!/usr/bin/env bash
# Example: thin wrapper using shared verbose helpers (preferred for stacks in this repo).
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
# Optional: remind operators about required variables (see nextcloud/prepare-stack.sh).
# prepare_stack_msg "before first deploy, set … in stack.env"

prepare_stack_copy_caddy
# Add the literal external prerequisites declared by this stack's Compose file:
# prepare_stack_ensure_docker_network "monitor"
# prepare_stack_ensure_docker_volume "shared_data"
prepare_stack_end
