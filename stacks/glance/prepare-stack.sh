#!/usr/bin/env bash
# Prepare local files before first deploy. Safe to re-run.
# Verbose helpers: scripts/prepare-stack-lib.sh
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy

mkdir -p "$_PREPDIR/config" "$_PREPDIR/assets"
if [[ ! -f "$_PREPDIR/config/glance.yml" ]]; then
  curl -fsSL -o "$_PREPDIR/config/glance.yml" \
    https://raw.githubusercontent.com/glanceapp/glance/main/docs/glance.yml
  prepare_stack_msg "downloaded config/glance.yml from upstream docs (edit widgets and feeds)."
else
  prepare_stack_msg "config/glance.yml already exists (left unchanged)."
fi
if [[ ! -f "$_PREPDIR/assets/user.css" ]]; then
  : > "$_PREPDIR/assets/user.css"
  prepare_stack_msg "created empty assets/user.css (optional custom CSS)."
fi

prepare_stack_ensure_docker_network "monitor"
prepare_stack_end
