#!/usr/bin/env bash
# Clone or update the PostHog upstream repo (required for ./prepare-stack.sh).
#
# Default first clone is shallow for speed (~). Set POSTHOG_FULL_CLONE=1 for a full clone
# (e.g. if you need an old tag or non-default history).
set -euo pipefail

_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$_ROOT"

if [[ -d posthog/.git ]]; then
  echo "[posthog/clone-repo] updating existing posthog/ ..."
  git -C posthog fetch origin
  branch="$(git -C posthog branch --show-current || true)"
  if [[ -n "${branch}" ]]; then
    git -C posthog reset --hard "origin/${branch}"
  else
    git -C posthog pull --ff-only || true
  fi
else
  echo "[posthog/clone-repo] cloning PostHog/posthog into posthog/ ..."
  if [[ "${POSTHOG_FULL_CLONE:-0}" == "1" ]]; then
    git clone --filter=blob:none https://github.com/PostHog/posthog.git posthog
  else
    git clone --depth 1 --filter=blob:none https://github.com/PostHog/posthog.git posthog
  fi
fi

echo "[posthog/clone-repo] done. Next: ./prepare-stack.sh"
