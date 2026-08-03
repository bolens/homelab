#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_example_to_env_path \
  "HEADSCALE_CONFIG_PATH" \
  "${XDG_CONFIG_HOME:-${HOME}/.config}/headscale/config.yaml" \
  "$_PREPDIR/config.example.yaml"
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "monitor"
prepare_stack_end
