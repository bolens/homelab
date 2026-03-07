#!/bin/bash
# Copy stack.env from example if missing; ensure acquis config path exists.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if [ ! -f stack.env ]; then
  cp stack.env.example stack.env
  echo "Created stack.env from stack.env.example"
fi
# Default acquis path (same default as docker-compose). Create dir and copy example if missing.
ACQUIS_DIR="${HOME:-/tmp}/.config/crowdsec"
ACQUIS_FILE="$ACQUIS_DIR/acquis.yaml"
if [ ! -f "$ACQUIS_FILE" ] && [ -n "${HOME}" ]; then
  mkdir -p "$ACQUIS_DIR"
  cp acquis.yaml.example "$ACQUIS_FILE"
  echo "Created $ACQUIS_FILE from acquis.yaml.example"
fi
