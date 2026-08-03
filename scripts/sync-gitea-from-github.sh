#!/usr/bin/env bash
# Fast-forward the Gitea mirror from the authoritative GitHub remote.
#
# This script never force-pushes or deletes refs. It refuses to continue if
# Gitea contains commits that are not ancestors of GitHub's branch.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
  echo "sync-gitea-from-github.sh: not inside a Git repository." >&2
  exit 1
fi
cd "$REPO_ROOT"

SOURCE_REMOTE="${SOURCE_REMOTE:-github}"
MIRROR_REMOTE="${MIRROR_REMOTE:-origin}"
BRANCH="${1:-main}"

for remote in "$SOURCE_REMOTE" "$MIRROR_REMOTE"; do
  if ! git remote get-url "$remote" >/dev/null 2>&1; then
    echo "sync-gitea-from-github.sh: required remote '$remote' is missing." >&2
    exit 1
  fi
done

echo "sync-gitea-from-github.sh: fetching $SOURCE_REMOTE/$BRANCH and tags..."
git fetch --prune --tags "$SOURCE_REMOTE" "$BRANCH"

source_ref="refs/remotes/$SOURCE_REMOTE/$BRANCH"
source_commit="$(git rev-parse --verify "$source_ref")"
mirror_commit="$(
  git ls-remote --exit-code "$MIRROR_REMOTE" "refs/heads/$BRANCH" 2>/dev/null |
    awk 'NR == 1 { print $1 }'
)" || true

if [[ -n "$mirror_commit" ]] &&
   ! git merge-base --is-ancestor "$mirror_commit" "$source_commit"; then
  echo "sync-gitea-from-github.sh: refusing to overwrite divergent $MIRROR_REMOTE/$BRANCH." >&2
  echo "  GitHub: $source_commit" >&2
  echo "  Gitea:  $mirror_commit" >&2
  echo "Resolve the divergence manually, then rerun this helper." >&2
  exit 1
fi

if [[ "$mirror_commit" == "$source_commit" ]]; then
  echo "sync-gitea-from-github.sh: $MIRROR_REMOTE/$BRANCH is current."
else
  echo "sync-gitea-from-github.sh: fast-forwarding $MIRROR_REMOTE/$BRANCH..."
  git push "$MIRROR_REMOTE" "$source_ref:refs/heads/$BRANCH"
fi

echo "sync-gitea-from-github.sh: mirroring GitHub tags without deleting Gitea refs..."
git push "$MIRROR_REMOTE" --tags
echo "sync-gitea-from-github.sh: synchronization complete at $source_commit."
