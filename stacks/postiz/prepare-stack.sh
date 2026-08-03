#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_msg "Postiz includes private PostgreSQL, Redis, and Temporal dependencies; first startup may take several minutes."
prepare_stack_ensure_docker_network "monitor"
prepare_stack_end
