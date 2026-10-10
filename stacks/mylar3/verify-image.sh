#!/usr/bin/env bash
# Verify an explicitly selected, already-pulled image. No live application mounts.
set -euo pipefail
if [[ $# != 1 ]]; then
  echo "Usage: $0 LOCAL_IMAGE_REFERENCE" >&2
  exit 2
fi
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "$script_dir/../.." && pwd)"
map_directory="$(mktemp -d)"
source_map="$map_directory/sources.json"
trap 'rm -f "$source_map"; rmdir "$map_directory"' EXIT
# Inventory output is exclusive; only Git-tracked public files can enter it.
python3 "$repo_dir/scripts/run-private-comic-controls.py" inventory mylar "$source_map"
chmod 0644 "$source_map"
docker image inspect "$1" >/dev/null
docker run --rm --pull=never --network=none --read-only --user=1000:1000 \
  --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=64 --memory=256m \
  --tmpfs /tmp:rw,size=64m,mode=1777 \
  -e PYTHONDONTWRITEBYTECODE=1 \
  --mount "type=bind,src=$script_dir/config,dst=/fixes,readonly" \
  --mount "type=bind,src=$repo_dir/scripts/run-private-comic-controls.py,dst=/ci-controls.py,readonly" \
  --mount "type=bind,src=$source_map,dst=/ci-source-map.json,readonly" \
  --entrypoint python3 "$1" -I -B /ci-controls.py mylar
