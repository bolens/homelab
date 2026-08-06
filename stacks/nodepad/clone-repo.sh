#!/usr/bin/env bash
set -euo pipefail
# Clone or update mskayyali/nodepad into ./repo for the Docker build context.
# After update, applies numbered patches from ./patches/*.patch (homelab overlays).
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
UPSTREAM_REVISION=5a6bad286c7cd2d57ccc5a1011991f8795f5dc80

apply_patches() {
  shopt -s nullglob
  local files=("$ROOT"/patches/*.patch)
  shopt -u nullglob
  if ((${#files[@]} == 0)); then
    return 0
  fi
  for f in "${files[@]}"; do
    echo "[clone-repo] applying $(basename "$f")..."
    (cd "$ROOT/repo" && patch --no-backup-if-mismatch -p1 <"$f") || {
      echo "[clone-repo] patch failed: $f (upstream may have changed — refresh the patch or fix hunks)" >&2
      exit 1
    }
  done
}

if [ -d "repo/.git" ]; then
  # Reset tracked files; remove untracked patch outputs but keep ignored build deps (node_modules, .next).
  git -C repo checkout -- .
  git -C repo clean -fd --exclude=node_modules --exclude=.next
  git -C repo fetch --depth 1 origin "$UPSTREAM_REVISION"
else
  git init repo
  git -C repo remote add origin https://github.com/mskayyali/nodepad.git
  git -C repo fetch --depth 1 origin "$UPSTREAM_REVISION"
fi
git -C repo checkout --detach "$UPSTREAM_REVISION"

apply_patches
