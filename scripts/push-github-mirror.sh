#!/usr/bin/env bash
# Compatibility wrapper retained for existing local commands.
set -euo pipefail

echo "push-github-mirror.sh: GitHub is authoritative; syncing Gitea from GitHub." >&2
exec "$(dirname "$0")/sync-gitea-from-github.sh" "$@"
