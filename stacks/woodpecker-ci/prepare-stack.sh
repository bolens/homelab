#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "ingress-admin"
prepare_stack_msg "Compose manages the agent identity volume; preserve an existing agent.conf before first adding its state mount"
# This local, application-owned state is created only on explicit opt-in.
if [[ "${WOODPECKER_PREPARE_PUBLISHER_BROKER:-0}" == 1 ]]; then
  for dir in publisher-broker/runtime publisher-broker/runtime/private \
    publisher-broker/runtime/state publisher-broker/runtime/state/replay \
    publisher-broker/runtime/state/leases publisher-broker/runtime/state/budgets; do
    if [[ -L "$dir" || ( -e "$dir" && ! -d "$dir" ) ]]; then
      prepare_stack_msg "refusing unsafe publisher broker directory"
      exit 1
    fi
    if [[ ! -d "$dir" ]]; then
      (umask 077; mkdir -- "$dir")
    fi
  done
  if [[ ! -e publisher-broker/runtime/private/config.json && ! -L publisher-broker/runtime/private/config.json ]]; then
    (umask 077; cp -- publisher-broker/config.json.example publisher-broker/runtime/private/config.json)
  fi
  prepare_stack_msg "publisher broker placeholders prepared; configure private files and matching UID/GID before explicit deployment"
fi
# docker-compose.cgroup-parent.yml.example is administrator-selected, never copied or activated.
prepare_stack_msg "optional cgroup-parent override and host slice require explicit administrator installation; preparation leaves both inactive"
prepare_stack_end
