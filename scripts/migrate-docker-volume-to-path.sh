#!/usr/bin/env bash
# Copy a Docker named volume to a host directory (e.g. when switching compose from
# named volumes to stack.env-controlled bind mounts). Uses a throwaway Alpine container.
#
# Usage:
#   ./scripts/migrate-docker-volume-to-path.sh VOLUME_NAME DEST_DIR [--chown UID:GID]
#
# Examples (volume names depend on compose project name; list with: docker volume ls):
#   ./scripts/migrate-docker-volume-to-path.sh caddy_caddy_data "$HOME/.local/share/caddy"
#   ./scripts/migrate-docker-volume-to-path.sh stacks_uptime-kuma_uptime_kuma_data \
#     "$HOME/.local/share/uptime-kuma" --chown 1000:1000
#
# Stop the stack before migrating. After verifying the app, remove the old volume:
#   docker volume rm VOLUME_NAME
set -euo pipefail

usage() {
  echo "Usage: $0 VOLUME_NAME DEST_DIR [--chown UID:GID]" >&2
  exit 1
}

[[ $# -ge 2 ]] || usage
VOL="${1:?}"
DEST="${2:?}"
shift 2

CHOWN_SPEC=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --chown)
      CHOWN_SPEC="${2:?}"
      shift 2
      ;;
    *)
      usage
      ;;
  esac
done

if ! docker volume inspect "$VOL" &>/dev/null; then
  echo "Error: volume not found: $VOL" >&2
  echo "Hint: docker volume ls | grep -i <stack>" >&2
  exit 1
fi

mkdir -p "$DEST"
# Copy preserving attributes; source mounted read-only.
docker run --rm \
  -v "${VOL}:/from:ro" \
  -v "${DEST}:/to" \
  alpine:3.21 \
  sh -c 'if [ -z "$(ls -A /from 2>/dev/null)" ]; then echo "/from is empty; nothing to copy."; exit 0; fi; cp -a /from/. /to/'

if [[ -n "$CHOWN_SPEC" ]]; then
  if [[ $(id -u) -eq 0 ]]; then
    chown -R "$CHOWN_SPEC" "$DEST"
  else
    sudo chown -R "$CHOWN_SPEC" "$DEST"
  fi
  echo "Ownership set to $CHOWN_SPEC on $DEST"
fi

echo "Done: $VOL → $DEST"
