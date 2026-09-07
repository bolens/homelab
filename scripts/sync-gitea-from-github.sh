#!/usr/bin/env bash
# Copy authoritative remote refs without using the caller's worktree or hooks.
# Existing destination refs are never force-pushed or deleted.
set -euo pipefail

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "sync-gitea-from-github.sh: not inside a Git repository." >&2
  exit 1
fi

# Keep relative remote paths anchored to the caller's repository root.
if [[ "$(git rev-parse --is-bare-repository)" == true ]]; then
  cd "$(git rev-parse --absolute-git-dir)"
else
  cd "$(git rev-parse --show-toplevel)"
fi

SOURCE_REMOTE="${SOURCE_REMOTE:-github}"
MIRROR_REMOTE="${MIRROR_REMOTE:-origin}"
BRANCH="${1:-main}"
MIRROR_BRANCH="${MIRROR_BRANCH:-$BRANCH}"
MIRROR_TAG_PREFIX="${MIRROR_TAG_PREFIX:-}"

for ref in "refs/heads/$BRANCH" "refs/heads/$MIRROR_BRANCH" "refs/tags/${MIRROR_TAG_PREFIX}probe"; do
  git check-ref-format "$ref" >/dev/null || {
    echo "sync-gitea-from-github.sh: invalid branch or tag prefix." >&2
    exit 2
  }
done
source_url="$(git remote get-url "$SOURCE_REMOTE")"
mirror_url="$(git remote get-url --push "$MIRROR_REMOTE")"

# Fetch only published source refs. A disposable bare repository also supports
# bare callers and keeps unrelated local tags, edits, and push hooks out of sync.
workspace="$(mktemp -d)"
trap 'rm -rf -- "$workspace"' EXIT
git init --bare --quiet "$workspace"
echo "sync-gitea-from-github.sh: fetching $SOURCE_REMOTE/$BRANCH and tags..."
git --git-dir="$workspace" fetch --no-tags "$source_url" \
  "refs/heads/$BRANCH:refs/heads/source" 'refs/tags/*:refs/source-tags/*'
source_commit="$(git --git-dir="$workspace" rev-parse --verify refs/heads/source)"

lookup_status=0
git --git-dir="$workspace" ls-remote --exit-code "$mirror_url" \
  "refs/heads/$MIRROR_BRANCH" >"$workspace/mirror-tip" || lookup_status=$?
case "$lookup_status" in
  0)
    # An advertised SHA is not necessarily present locally. Fetch its branch
    # before ancestry checks; a raced update is checked at the fetched tip.
    git --git-dir="$workspace" fetch --no-tags "$mirror_url" \
      "refs/heads/$MIRROR_BRANCH:refs/heads/mirror"
    mirror_commit="$(git --git-dir="$workspace" rev-parse --verify refs/heads/mirror)"
    if ! git --git-dir="$workspace" merge-base --is-ancestor "$mirror_commit" "$source_commit"; then
      echo "sync-gitea-from-github.sh: refusing to overwrite divergent $MIRROR_REMOTE/$MIRROR_BRANCH." >&2
      exit 1
    fi
    ;;
  2) mirror_commit="" ;;
  *)
    echo "sync-gitea-from-github.sh: destination lookup failed; no refs pushed." >&2
    exit "$lookup_status"
    ;;
esac

if [[ "$mirror_commit" == "$source_commit" ]]; then
  echo "sync-gitea-from-github.sh: $MIRROR_REMOTE/$MIRROR_BRANCH is current."
else
  echo "sync-gitea-from-github.sh: fast-forwarding $MIRROR_REMOTE/$MIRROR_BRANCH..."
  git --git-dir="$workspace" push "$mirror_url" "refs/heads/source:refs/heads/$MIRROR_BRANCH"
fi

if [[ -n "$(git --git-dir="$workspace" for-each-ref --format='%(refname)' refs/source-tags/)" ]]; then
  echo "sync-gitea-from-github.sh: copying published source tags without replacing destination tags..."
  git --git-dir="$workspace" push "$mirror_url" "refs/source-tags/*:refs/tags/$MIRROR_TAG_PREFIX*"
fi
echo "sync-gitea-from-github.sh: synchronization complete at $source_commit."
