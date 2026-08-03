#!/usr/bin/env bash
set -euo pipefail

if command -v zizmor >/dev/null 2>&1; then
  exec zizmor --min-severity medium --min-confidence medium --offline .
fi

if command -v docker >/dev/null 2>&1 &&
   docker info >/dev/null 2>&1; then
  repo_root="$(git rev-parse --show-toplevel)"
  exec docker run --rm \
    --volume "$repo_root:/repo:ro" \
    --workdir /repo \
    ghcr.io/zizmorcore/zizmor:1.29.0 \
    --min-severity medium \
    --min-confidence medium \
    --offline .
fi

echo "pre-commit-zizmor.sh: install zizmor or provide Docker access." >&2
echo "See https://docs.zizmor.sh/installation/" >&2
exit 1
