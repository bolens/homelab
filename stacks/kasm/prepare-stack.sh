#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_msg "CPU-only hosts: copy docker-compose.override.yml.example to docker-compose.override.yml; leave it absent when NVIDIA support is configured."
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "backup" true
prepare_stack_ensure_docker_network "proxy-ingress"
prepare_stack_end
