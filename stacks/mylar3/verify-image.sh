#!/usr/bin/env bash
# Verify an explicitly selected, already-pulled image. No live application mounts.
set -euo pipefail
if [[ $# != 1 ]]; then
  echo "Usage: $0 LOCAL_IMAGE_REFERENCE" >&2
  exit 2
fi
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
docker image inspect "$1" >/dev/null
docker run --rm --pull=never --network=none --read-only --user=1000:1000 \
  --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=64 --memory=256m \
  --tmpfs /tmp:rw,size=64m,mode=1777 \
  -e PYTHONDONTWRITEBYTECODE=1 \
  --mount "type=bind,src=$script_dir/config,dst=/fixes,readonly" \
  --entrypoint python3 "$1" /fixes/verify_image.py
