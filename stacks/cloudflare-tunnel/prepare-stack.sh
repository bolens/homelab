#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

if [[ ! -f "$_PREPDIR/config.yml" ]]; then
  cp "$_PREPDIR/config.yml.example" "$_PREPDIR/config.yml"
  prepare_stack_msg "created config.yml from config.yml.example — set ingress rules and TUNNEL_TOKEN in stack.env."
else
  prepare_stack_msg "config.yml already exists (left unchanged)."
fi

prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "monitor"
prepare_stack_end
