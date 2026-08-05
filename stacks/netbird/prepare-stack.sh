#!/usr/bin/env bash
# Prepare local files before first deploy. Safe to re-run: existing files are not overwritten.
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

if [[ ! -f dashboard.env ]] && [[ -f dashboard.env.example ]]; then
  cp dashboard.env.example dashboard.env
  prepare_stack_msg "created dashboard.env from dashboard.env.example — set public URLs to match config.yaml."
else
  prepare_stack_msg "dashboard.env already exists or no example (skipped)."
fi

if [[ ! -f config.yaml ]] && [[ -f config.yaml.example ]]; then
  cp config.yaml.example config.yaml
  prepare_stack_msg "created config.yaml from config.yaml.example — set authSecret, encryptionKey, and hostnames before docker compose up."
else
  prepare_stack_msg "config.yaml already exists or no example (skipped)."
fi

prepare_stack_copy_caddy

prepare_stack_ensure_docker_network "ingress-admin"
prepare_stack_end
