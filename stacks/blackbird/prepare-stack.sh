#!/bin/bash
# Create stack.env from example if missing; create .env from BLACKBIRD_IMAGE for compose image resolution
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if [ ! -f stack.env ]; then
  cp stack.env.example stack.env
  echo "Created stack.env from stack.env.example"
fi
if [ -f stack.env ] && grep -q "^BLACKBIRD_IMAGE=" stack.env; then
  grep "^BLACKBIRD_IMAGE=" stack.env > .env
  echo "Updated .env from BLACKBIRD_IMAGE in stack.env"
fi
