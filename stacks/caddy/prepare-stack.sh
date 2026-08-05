#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

if [[ ! -f "$_PREPDIR/Caddyfile" ]]; then
  cp "$_PREPDIR/Caddyfile.example" "$_PREPDIR/Caddyfile"
  prepare_stack_msg "created Caddyfile from Caddyfile.example — add snippet imports and set CLOUDFLARE_API_TOKEN in stack.env."
else
  prepare_stack_msg "Caddyfile already exists (left unchanged)."
fi

prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "monitor"
prepare_stack_ensure_docker_network "proxy-ingress"
prepare_stack_end
