#!/usr/bin/env bash
# Prepare local files before first deploy. Safe to re-run: existing stack.env and caddy_snippet.conf are not overwritten.
# Verbose helpers: scripts/prepare-stack-lib.sh — see scripts/prepare-stack.examples/
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

prepare_stack_msg "optional docker-compose.override.example is only for a locally built official AIL 7.x image; copy it manually after reading the README."
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "security-research"
prepare_stack_ensure_docker_network "ingress-admin"
prepare_stack_end
