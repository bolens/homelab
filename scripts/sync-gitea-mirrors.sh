#!/usr/bin/env bash
# Example: synchronize authoritative GitHub repositories to Gitea backups.
# Copy to sync-gitea-mirrors.local.sh and configure the ignored local copy.
set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SYNC_HELPER="$SCRIPT_DIR/sync-gitea-from-github.sh"

repositories=(
  "example-app|$HOME/dev/example-app|origin|backup"
  "example-infrastructure|$HOME/dev/example-infrastructure|github|gitea"
)

failures=0

for entry in "${repositories[@]}"; do
  IFS='|' read -r name path source_remote backup_remote <<< "$entry"

  echo "sync-gitea-mirrors.sh: syncing $name ($source_remote -> $backup_remote)..."
  if [[ ! -d "$path/.git" ]]; then
    echo "sync-gitea-mirrors.sh: repository is missing: $path" >&2
    failures=$((failures + 1))
    continue
  fi

  if ! (
    cd "$path"
    SOURCE_REMOTE="$source_remote" MIRROR_REMOTE="$backup_remote" \
      bash "$SYNC_HELPER" main
  ); then
    echo "sync-gitea-mirrors.sh: synchronization failed for $name." >&2
    failures=$((failures + 1))
  fi
done

if (( failures > 0 )); then
  echo "sync-gitea-mirrors.sh: $failures repository synchronization(s) failed." >&2
  exit 1
fi

echo "sync-gitea-mirrors.sh: all repositories synchronized successfully."
