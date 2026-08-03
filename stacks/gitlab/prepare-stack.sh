#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_msg "GitLab may take ten minutes or more to become healthy on first boot."
prepare_stack_msg "verify GITLAB_SSH_PORT is unused and matches the public clone URL configuration."
prepare_stack_ensure_docker_network "monitor"
prepare_stack_end
