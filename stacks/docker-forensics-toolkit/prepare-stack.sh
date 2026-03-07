#!/bin/bash
# Create stack.env from example if missing; create .env from DOCKER_FORENSICS_TOOLKIT_IMAGE for compose image resolution
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if [ ! -f stack.env ]; then
  cp stack.env.example stack.env
  echo "Created stack.env from stack.env.example"
fi
if [ -f stack.env ] && grep -q "^DOCKER_FORENSICS_TOOLKIT_IMAGE=" stack.env; then
  grep "^DOCKER_FORENSICS_TOOLKIT_IMAGE=" stack.env > .env
  echo "Updated .env from DOCKER_FORENSICS_TOOLKIT_IMAGE in stack.env"
fi
