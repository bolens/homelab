#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_msg "the Docker socket grants jobs effective control of this host; register only trusted projects and keep privileged mode disabled."
prepare_stack_msg "after deployment, register with: docker exec -it gitlab-runner gitlab-runner register"
prepare_stack_end
