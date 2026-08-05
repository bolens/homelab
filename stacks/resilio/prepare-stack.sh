#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "proxy-ingress"
prepare_stack_ensure_docker_volume "resilio_config"
prepare_stack_ensure_docker_volume "resilio_sync"
prepare_stack_ensure_dir_from_env "RESILIO_DOWNLOADS_PATH" "/mnt/unraid/media/downloads/resilio"
prepare_stack_end
