#!/usr/bin/env bash
# Clone the Holehe Web Checker repo into ./repo (required once before first docker compose up).
set -e
REPO_URL="${HOLEHE_WEB_REPO_URL:-https://github.com/sds-osint/holehe-web.git}"
REPO_DIR="${1:-repo}"
if [[ -d "$REPO_DIR/.git" ]]; then
  echo "Repo already at $REPO_DIR; pull latest? (y/n)"
  read -r r
  if [[ "$r" = y ]]; then
    git -C "$REPO_DIR" pull
  fi
  exit 0
fi
git clone --depth 1 "$REPO_URL" "$REPO_DIR"
echo "Cloned holehe-web into $REPO_DIR. Run: docker compose up -d"

