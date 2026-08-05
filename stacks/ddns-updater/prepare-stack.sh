#!/usr/bin/env bash
# Prepare local files before first deploy. Safe to re-run: existing stack.env and caddy_snippet.conf are not overwritten.
# Verbose helpers: scripts/prepare-stack-lib.sh — see scripts/prepare-stack.examples/
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

prepare_stack_msg "Ensuring data directory and config.json..."
mkdir -p "$_PREPDIR/data"
if [[ ! -f "$_PREPDIR/data/config.json" ]]; then
  cp "$_PREPDIR/config.json.example" "$_PREPDIR/data/config.json"
  prepare_stack_msg "Created data/config.json from config.json.example (add provider settings per upstream docs)."
else
  prepare_stack_msg "data/config.json already exists (left unchanged)."
fi
prepare_stack_msg "If the container cannot write updates.json, run: chown -R 1000:1000 \"$_PREPDIR/data\""

prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "ingress-admin"
prepare_stack_end
