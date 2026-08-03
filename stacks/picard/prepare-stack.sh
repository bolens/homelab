#!/usr/bin/env bash
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "monitor"
prepare_stack_ensure_dir_from_env "PICARD_MUSIC_PATH" "/mnt/unraid/media/music"
prepare_stack_ensure_dir_from_env "PICARD_IMPORT_PATH" "/mnt/unraid/media/downloads/soulseek"
prepare_stack_end
