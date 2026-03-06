#!/usr/bin/env bash
set -euo pipefail

# Clone or update the community logseq-sync backend into ./repo.
# Upstream: https://github.com/bcspragu/logseq-sync

REPO_DIR="repo"
REPO_URL="https://github.com/bcspragu/logseq-sync.git"

if [ -d "${REPO_DIR}/.git" ]; then
  echo "Updating existing logseq-sync repo in ${REPO_DIR}..."
  git -C "${REPO_DIR}" pull --ff-only
else
  echo "Cloning logseq-sync into ${REPO_DIR}..."
  git clone "${REPO_URL}" "${REPO_DIR}"
fi

echo "Done. You can now build and run the stack with:"
echo "  docker compose build"
echo "  docker compose up -d"

