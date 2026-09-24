#!/usr/bin/env bash
set -euo pipefail
umask 077
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_ensure_dir_from_env "KOMGA_COMICS_PATH" "${MEDIA_ROOT:-/srv/media}/comics" require-existing
prepare_stack_ensure_dir_from_env "KOMGA_MANGA_PATH" "${MEDIA_ROOT:-/srv/media}/manga" require-existing
prepare_stack_ensure_dir_from_env "NORMALIZER_STATE_PATH" "./normalizer-state" require-existing
prepare_stack_copy_example_to_env_path "NORMALIZER_CONFIG_PATH" "./normalizer.json" "normalizer/normalizer.json.example"
prepare_stack_ensure_docker_network "ingress-public"
prepare_stack_ensure_docker_network "media-automation"
prepare_stack_msg "Set the Komga API key in normalizer.json. Verify PUID/PGID own the state and media paths and can write the Komga config volume before enabling the override."
prepare_stack_end
