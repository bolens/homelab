#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_dir_from_env "ERSATZTV_MEDIA_PATH" "/path/to/media" "require-existing"
prepare_stack_ensure_docker_network "ingress-admin"
prepare_stack_ensure_docker_network "media-services"
prepare_stack_msg "No native form login: protect the public hostname with Cloudflare Access before publishing it; keep playlist/guide playback private."
prepare_stack_msg "Optional NVIDIA acceleration: review docker-compose.nvidia.yml and explicitly enable it after checking the host GPU and NVIDIA Container Toolkit."
prepare_stack_msg "Optional correctness monitoring and verified online backups: review Dispatcharr's host maintenance integration; preparation does not install jobs or change application schedules."
prepare_stack_end
