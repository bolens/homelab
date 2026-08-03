#!/usr/bin/env bash
# CI / local: refresh upstream, apply all patches, run a production Next.js build.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
./clone-repo.sh
if ! command -v npm >/dev/null 2>&1; then
  echo "[verify-patches] npm not found; clone-repo.sh only — exiting 0."
  exit 0
fi
(cd "$ROOT/repo" && npm ci && npm run build)
echo "[verify-patches] OK: patches applied and next build succeeded."
