#!/usr/bin/env bash
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
if [[ -f stack.env ]] && [[ ! -e .env ]]; then
  ln -sf stack.env .env
  prepare_stack_msg "linked .env -> stack.env so docker compose picks variables for interpolation."
elif [[ -f .env ]]; then
  prepare_stack_msg ".env already exists (left unchanged; not linking to stack.env)."
fi
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "ingress-sensitive"
prepare_stack_ensure_docker_network "mail-clients" "true"
prepare_stack_end
