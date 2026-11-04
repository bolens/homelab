#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
if grep -q '^IMMICH_LIBRARY_PATH=' stack.env; then
  prepare_stack_ensure_dir_from_env "IMMICH_LIBRARY_PATH" "/srv/media/photos/immich" "require-existing"
fi
prepare_stack_msg "Optional docker-compose.storage.yml binds finalized originals; set IMMICH_LIBRARY_PATH, verify the mounted filesystem, and select the override explicitly."
prepare_stack_ensure_docker_network "ingress-public"
prepare_stack_ensure_docker_network "telemetry" "true"
prepare_stack_end
