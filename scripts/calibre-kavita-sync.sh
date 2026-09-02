#!/usr/bin/env bash
set -euo pipefail

calibre_container=${CALIBRE_CONTAINER:-calibre-web}
kavita_container=${KAVITA_CONTAINER:-kavita}
kavita_db=${KAVITA_DB:-/mnt/apps/system/docker/volumes/kavita_kavita_config/_data/kavita.db}
export_dir=${KAVITA_EXPORT_DIR:-/mnt/unraid/media/kavita-books}
export_user=${KAVITA_EXPORT_USER:-panda}
stage_dir=

cleanup() {
  if [[ -n "$stage_dir" && -d "$stage_dir" ]]; then
    runuser -u "$export_user" -- rm -rf -- "$stage_dir"
  fi
  docker exec "$calibre_container" rm -rf -- /tmp/kavita-export
}
trap cleanup EXIT

for command in docker rsync runuser sqlite3; do
  command -v "$command" >/dev/null || {
    printf 'Required command not found: %s\n' "$command" >&2
    exit 1
  }
done

[[ "$export_dir" == /* && "$export_dir" != / ]] || {
  printf 'KAVITA_EXPORT_DIR must be an absolute non-root path\n' >&2
  exit 1
}
[[ -f "$kavita_db" ]] || {
  printf 'Kavita database not found: %s\n' "$kavita_db" >&2
  exit 1
}

docker inspect --format '{{.State.Running}}' "$calibre_container" | grep -qx true
docker inspect --format '{{.State.Running}}' "$kavita_container" | grep -qx true

calibredb_ready=false
for _ in $(seq 1 60); do
  if docker exec "$calibre_container" sh -c \
    'command -v calibredb >/dev/null && command -v ebook-convert >/dev/null'; then
    calibredb_ready=true
    break
  fi
  sleep 10
done
[[ "$calibredb_ready" == true ]] || {
  printf 'Calibre tools were not ready after 10 minutes\n' >&2
  exit 1
}

runuser -u "$export_user" -- mkdir -p -- "$export_dir"
stage_dir=$(runuser -u "$export_user" -- \
  mktemp -d "${export_dir%/*}/.kavita-books-stage.XXXXXX")
runuser -u "$export_user" -- chmod 0775 "$stage_dir"

export_template="{series:'re(ifempty(\$,field('title')),':',' -')'}/{series:'re(ifempty(\$,field('title')),':',' -')'}{series_index:0>2s| - |} - {id}"

docker exec --user 1000:1000 "$calibre_container" bash -c '
  set -eu
  rm -rf -- /tmp/kavita-export
  mkdir -p /tmp/kavita-export
'
docker exec --user 1000:1000 "$calibre_container" \
  calibredb export --all --with-library /books \
  --to-dir /tmp/kavita-export \
  --template "$export_template" \
  --dont-save-cover \
  --dont-write-opf
docker exec --user 1000:1000 "$calibre_container" bash -c '
  set -eu
  find /tmp/kavita-export -type f \( -iname "*.azw3" -o -iname "*.mobi" \) -print0 |
    while IFS= read -r -d "" source; do
      target=${source%.*}.epub
      ebook-convert "$source" "$target" >/dev/null
      rm -f -- "$source"
    done
'

docker exec "$calibre_container" tar -C /tmp/kavita-export -cf - . |
  runuser -u "$export_user" -- tar -C "$stage_dir" -xf -
runuser -u "$export_user" -- rsync -rlt --delete -- "$stage_dir/" "$export_dir/"

auth_key=$(sqlite3 -readonly "$kavita_db" \
  "select Key from AppUserAuthKey where ExpiresAtUtc is null order by Id limit 1;")
[[ -n "$auth_key" ]] || {
  printf 'No non-expiring Kavita auth key is available\n' >&2
  exit 1
}
printf '%s\n' "$auth_key" | docker exec -i "$kavita_container" sh -c '
  IFS= read -r auth_key
  curl -fsS -X POST -H "x-api-key: $auth_key" \
    http://127.0.0.1:5000/api/Library/scan-all >/dev/null
'

printf 'Calibre export synchronized to %s and Kavita scan requested\n' "$export_dir"
