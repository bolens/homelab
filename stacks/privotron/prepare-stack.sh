#!/bin/bash
# Create stack.env from example if missing; sync PRIVOTRON_IMAGE to .env for compose
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if [ ! -f stack.env ]; then
  cp stack.env.example stack.env
  echo "Created stack.env from stack.env.example"
fi
if [ -f stack.env ] && grep -q "^PRIVOTRON_IMAGE=" stack.env; then
  grep "^PRIVOTRON_IMAGE=" stack.env > .env
  echo "Updated .env from PRIVOTRON_IMAGE in stack.env"
fi
