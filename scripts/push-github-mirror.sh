#!/usr/bin/env bash
# Push current branch to origin (Gitea) and to remote "github" if configured.
# Prefer Gitea "push mirror" to GitHub for hands-off backup; use this when you mirror manually.
#
# Usage:
#   ./scripts/push-github-mirror.sh           # current branch
#   ./scripts/push-github-mirror.sh main
set -euo pipefail

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
  echo "push-github-mirror.sh: not inside a git repository." >&2
  exit 1
fi
cd "$REPO_ROOT"

echo "push-github-mirror.sh: pushing branch '$BRANCH' to origin..."
git push origin "$BRANCH"

if git remote get-url github >/dev/null 2>&1; then
  echo "push-github-mirror.sh: pushing branch '$BRANCH' to github..."
  git push github "$BRANCH"
else
  echo "push-github-mirror.sh: no remote named 'github' — skipping. Add with:" >&2
  echo "  git remote add github https://github.com/USER/REPO.git" >&2
  echo "Or configure a push mirror in Gitea (see documents/DEVELOPMENT-WORKFLOW.md)." >&2
fi
