#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "ingress-public"
prepare_stack_msg "Stoat config and secrets are operator-owned; preparation does not generate or overwrite them."
prepare_stack_msg "Before deployment, review STOAT_CONFIG_DIR and STOAT_SECRETS_FILE and provide stoat.json."
prepare_stack_end
