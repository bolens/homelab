#!/usr/bin/env bash
# Compatibility entry point; the reconciler is implemented in Python.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/sync-local-hosts.py" "$@"
