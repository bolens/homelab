#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"

if [[ ! -f "$_PREPDIR/docker-compose.override.yml" ]]; then
  cp "$_PREPDIR/docker-compose.override.yml.example" "$_PREPDIR/docker-compose.override.yml"
  prepare_stack_msg "created docker-compose.override.yml from example — adjust bind mounts and caddy network."
else
  prepare_stack_msg "docker-compose.override.yml already exists (left unchanged)."
fi

prepare_stack_copy_caddy
prepare_stack_end
