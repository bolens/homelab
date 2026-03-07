#!/bin/bash
# Create data dir, stack.env from example if missing; sync METAGOOFIL_IMAGE to .env for compose
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
DATA_DIR="${METAGOOFIL_DATA_PATH:-$HOME/.config/metagoofil/data}"
mkdir -p "$DATA_DIR"
if [ ! -f stack.env ]; then
  cp stack.env.example stack.env
  echo "Created stack.env from stack.env.example"
fi
if [ -f stack.env ] && grep -q "^METAGOOFIL_IMAGE=" stack.env; then
  grep "^METAGOOFIL_IMAGE=" stack.env > .env
  echo "Updated .env from METAGOOFIL_IMAGE in stack.env"
fi
echo "Data dir: $DATA_DIR"
