#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "ingress-public"
prepare_stack_msg "Seafile 14: review REDIS_PASSWORD and JWT_PRIVATE_KEY in stack.env; existing values are never replaced."
prepare_stack_msg "Existing installations: follow README.md migration and verified-backup steps before deployment; preparation does not migrate application settings."
prepare_stack_msg "Fresh installs also require INIT_SEAFILE_ADMIN_EMAIL and INIT_SEAFILE_ADMIN_PASSWORD."
prepare_stack_end
