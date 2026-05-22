#!/usr/bin/env bash
# Example: env + Caddy from the shared lib, with extra steps in the middle (mkdir, config copies, etc.).
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

prepare_stack_msg "ensuring local config directory exists..."
mkdir -p ./config
# cp ./some.conf.example ./config/some.conf  # example

prepare_stack_copy_caddy
prepare_stack_end
