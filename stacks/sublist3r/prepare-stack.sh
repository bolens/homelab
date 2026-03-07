#!/bin/bash
# Create results dir, copy stack.env from example if missing
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
RESULTS_DIR="${SUBLIST3R_RESULTS_PATH:-$HOME/.config/sublist3r/results}"
mkdir -p "$RESULTS_DIR"
if [ ! -f stack.env ]; then
  cp stack.env.example stack.env
  echo "Created stack.env from stack.env.example"
fi
echo "Results dir: $RESULTS_DIR"
