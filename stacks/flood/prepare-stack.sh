#!/usr/bin/env bash
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "ingress-admin"
prepare_stack_ensure_docker_network "torrents"
prepare_stack_ensure_docker_volume "torrents_manual"
prepare_stack_msg "Flood uses --rundir=/data. Migrate and verify existing home-directory runtime state before recreation. Librarr storage is opt-in; verify its remote mount and existing directories first."
prepare_stack_end
