#!/usr/bin/env bash
# Synchronize authoritative GitHub repositories to their Gitea backups.
set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SYNC_HELPER="$SCRIPT_DIR/sync-gitea-from-github.sh"

repositories=(
  "homelab|$HOME/dev/docker|github|origin"
  "uddns|$HOME/dev/uddns|origin|backup"
  "audio-utils|$HOME/dev/audio-utils|origin|backup"
  "millennium-helpers|$HOME/dev/millennium-helpers|origin|backup"
  "aur-response-toolkit|$HOME/dev/aur-response-toolkit|origin|backup"
  "appicon|$HOME/dev/appicon|origin|backup"
  "launch-layer|/mnt/games/launch-layer|origin|backup"
  "bolens-profile|$HOME/dev/bolens-profile|origin|backup"
  "ps-profile|$HOME/dev/ps-profile|origin|backup"
  "ufw|$HOME/dev/ufw|origin|backup"
  "waybar-config|$HOME/dev/waybar-config|origin|backup"
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
