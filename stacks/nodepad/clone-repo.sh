#!/usr/bin/env bash
set -euo pipefail
# Clone or update mskayyali/nodepad into ./repo for the Docker build context.
# After update, applies numbered patches from ./patches/*.patch (homelab overlays).
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

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
  git -C repo pull --rebase
else
  git clone --depth 1 https://github.com/mskayyali/nodepad.git repo
fi

apply_patches
