#!/bin/bash
# Start API + client dev servers. Run from `client/` after `pnpm install` at the repo root.

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
(cd "$ROOT/api" && pnpm run dev) &
cd "$(dirname "$0")"
pnpm exec vp dev
