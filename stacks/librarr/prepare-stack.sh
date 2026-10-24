#!/usr/bin/env bash
set -euo pipefail
umask 077
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_dir_from_env "LIBRARR_MEDIA_PATH" "${MEDIA_ROOT:-/srv/media}" require-existing
prepare_stack_ensure_dir_from_env "LIBRARR_CONFIG_PATH" "${LAB_ROOT:-/srv/lab}/librarr"
if [[ ! -e sources.json ]]; then
  cp sources.json.example sources.json
  prepare_stack_msg "created sources.json from reviewed public examples. Existing source registries are preserved."
fi
prepare_stack_ensure_docker_network "ingress-admin"
prepare_stack_ensure_docker_network "media-automation"
prepare_stack_ensure_docker_network "torrents"
prepare_stack_msg "Set authentication and integration credentials privately. Verify config ownership matches PUID/PGID."
prepare_stack_msg "Reader networking is opt-in with docker-compose.readers.yml; ensure ingress-public exists before selecting it."
prepare_stack_msg "Flood is opt-in: verify its mounted download paths, persistent accounts and socket volume before selecting docker-compose.flood.yml."
prepare_stack_end
