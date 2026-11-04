#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
if [[ ! -f config.json ]]; then
  cp config.json.example config.json
  chmod 600 config.json
fi
prepare_stack_msg "seed a valid native authentication hash before startup; see README. Existing config is preserved."
prepare_stack_ensure_docker_network "ingress-sensitive"
prepare_stack_end
