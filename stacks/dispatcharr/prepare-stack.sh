#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "ingress-admin"
prepare_stack_msg "Optional same-host Plex access: review docker-compose.plex.yml and enable it explicitly; preparation does not publish a port."
prepare_stack_msg "Optional ErsatzTV program posters: review docker-compose.library-artwork.yml, set its HTTPS image origin, and apply the private-guide denial and strict image exception before enabling it."
prepare_stack_msg "Optional DVR storage: review docker-compose.storage.yml; verify the media mount and create the recordings directory before enabling it."
prepare_stack_msg "Optional maintenance: review maintenance/ and the README; preparation never installs host jobs or enables channel deletion."
prepare_stack_end
