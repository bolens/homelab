#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
# Preserve existing configuration; never append hostname permissions automatically.
printf '%s\n' 'Review CLARK_CDP_ORIGINS in stack.env before enabling hostname ingress; existing values are preserved.'
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "ingress-admin"
prepare_stack_end
