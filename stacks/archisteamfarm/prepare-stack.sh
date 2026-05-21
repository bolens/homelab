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
# ASF config dir: from stack.env (sanitized example uses ./config)
# prepare-stack.sh copies ASF.json.example there and writes .env for compose volume.
if [ -f "stack.env" ]; then
  # shellcheck source=/dev/null
  source stack.env 2>/dev/null || true
fi
ASF_CONFIG_DIR="${ASF_CONFIG_DIR:-./config}"
# Expand leading ~ only; use literal ~ so we don't match already-absolute paths ([[ ~* ]] would match $HOME/*)
if [[ "$ASF_CONFIG_DIR" == '~'* ]]; then
  ASF_CONFIG_DIR="${HOME}${ASF_CONFIG_DIR#\~}"
fi
echo "ASF config dir: $ASF_CONFIG_DIR"
mkdir -p "$ASF_CONFIG_DIR"
if [ -f "ASF.json.example" ] && [ ! -f "$ASF_CONFIG_DIR/ASF.json" ]; then
  cp ASF.json.example "$ASF_CONFIG_DIR/ASF.json"
  echo "Created $ASF_CONFIG_DIR/ASF.json from ASF.json.example"
elif [ -f "$ASF_CONFIG_DIR/ASF.json" ]; then
  echo "ASF.json already exists in $ASF_CONFIG_DIR (skipped copy)"
elif [ ! -f "ASF.json.example" ]; then
  echo "Warning: ASF.json.example not found in $(pwd), cannot copy to $ASF_CONFIG_DIR"
fi
if [ -f "IPC.config.example" ] && [ ! -f "$ASF_CONFIG_DIR/IPC.config" ]; then
  cp IPC.config.example "$ASF_CONFIG_DIR/IPC.config"
  echo "Created $ASF_CONFIG_DIR/IPC.config from IPC.config.example"
elif [ -f "$ASF_CONFIG_DIR/IPC.config" ]; then
  echo "IPC.config already exists in $ASF_CONFIG_DIR (skipped copy)"
elif [ ! -f "IPC.config.example" ]; then
  echo "Warning: IPC.config.example not found in $(pwd), cannot copy to $ASF_CONFIG_DIR"
fi
# So docker-compose can use ASF_CONFIG_DIR in the volume mount
echo "ASF_CONFIG_DIR=$ASF_CONFIG_DIR" > .env
echo "Wrote ASF_CONFIG_DIR to .env for docker-compose"

prepare_stack_copy_caddy
prepare_stack_end
