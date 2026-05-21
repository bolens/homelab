#!/usr/bin/env bash
# Prepare local files before first deploy. Safe to re-run: existing stack.env and caddy_snippet.conf are not overwritten.
# Verbose helpers: scripts/prepare-stack-lib.sh — see scripts/prepare-stack.examples/
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

prepare_stack_msg "stack-specific steps..."
if [ ! -f "repo/package.json" ]; then
  echo "Run ./clone-repo.sh before docker compose build (clones upstream + applies patches/0001–0006 in order)."
else
  echo "./repo is present; ./clone-repo.sh refreshes upstream and re-applies patches; optional ./verify-patches.sh; then docker compose build && docker compose up -d (runtime env: stack.env via env_file — see README)."
fi

prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "monitor"
prepare_stack_end
