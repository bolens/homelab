#!/usr/bin/env bash
set -euo pipefail

calibre_container=${CALIBRE_CONTAINER:-calibre-web}
kavita_container=${KAVITA_CONTAINER:-kavita}
kavita_db=${KAVITA_DB:-/mnt/apps/system/docker/volumes/kavita_kavita_config/_data/kavita.db}
export_dir=${KAVITA_EXPORT_DIR:-/mnt/unraid/media/kavita-books}
export_user=${KAVITA_EXPORT_USER:-panda}
source_mount=${CALIBRE_SOURCE_MOUNT:-/mnt/unraid/media}
export_mount=${KAVITA_EXPORT_MOUNT:-/mnt/unraid/media}
lock_file=${KAVITA_SYNC_LOCK:-/run/lock/calibre-kavita-sync.lock}
calibre_uid=${CALIBRE_EXPORT_UID:-1000}
calibre_gid=${CALIBRE_EXPORT_GID:-1000}
include_unregistered=${CALIBRE_INCLUDE_UNREGISTERED_EPUBS:-false}
import_planner=${CALIBRE_IMPORT_PLANNER:-/usr/local/libexec/calibre-catalog-import}
normalize_legacy=${CALIBRE_NORMALIZE_LEGACY_EPUBS:-false}
stage_dir=
container_stage=
container_work=
manifest_before=
manifest_after=
private_run=
umask 077

cleanup() {
  if [[ -n "$stage_dir" && -d "$stage_dir" ]]; then
    runuser -u "$export_user" -- rm -rf -- "$stage_dir"
  fi
  if [[ -n "$container_work" ]]; then
    docker exec --user "$calibre_uid:$calibre_gid" "$calibre_container" rm -rf -- "$container_work"
  fi
  [[ -z "$manifest_before" ]] || rm -f -- "$manifest_before"
  [[ -z "$manifest_after" ]] || rm -f -- "$manifest_after"
  [[ -z "$private_run" ]] || rm -rf -- "$private_run"
}

for command in docker rsync runuser sqlite3 flock findmnt realpath python3 tar; do
  command -v "$command" >/dev/null || {
    printf 'Required command not found: %s\n' "$command" >&2
    exit 1
  }
done
for setting in "$include_unregistered" "$normalize_legacy"; do
  [[ "$setting" == true || "$setting" == false ]] || {
    printf 'Calibre export boolean settings must be true or false\n' >&2
    exit 1
  }
done
if [[ "$include_unregistered" == true && ! -x "$import_planner" ]]; then
  printf 'The configured Calibre catalog planner is not executable\n' >&2
  exit 1
fi

exec 9>"$lock_file"
if ! flock -n 9; then
  printf 'Calibre export is already running; skipped\n'
  exit 0
fi
trap cleanup EXIT

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
source_path=$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/books"}}{{.Source}}{{end}}{{end}}' "$calibre_container")
[[ -d "$source_path" && -f "$source_path/metadata.db" ]] || {
  printf 'The Calibre source library is missing\n' >&2
  exit 1
}
source_mount=$(realpath -e -- "$source_mount")
export_mount=$(realpath -e -- "$export_mount")
source_path=$(realpath -e -- "$source_path")
export_dir=$(realpath -m -- "$export_dir")

require_mounts() {
  local ancestor target
  findmnt -rn -M "$source_mount" >/dev/null
  findmnt -rn -M "$export_mount" >/dev/null
  [[ "$source_path/" == "$source_mount/"* && "$export_dir/" == "$export_mount/"* ]] || {
    printf 'Source or export path is outside its required filesystem mount\n' >&2
    return 1
  }
  target=$(findmnt -rn -T "$source_path" -o TARGET)
  [[ "$target" == "$source_mount" ]] || {
    printf 'The Calibre source filesystem mount is not available\n' >&2
    return 1
  }
  ancestor=$export_dir
  while [[ ! -e "$ancestor" && "$ancestor" != / ]]; do
    ancestor=${ancestor%/*}
    [[ -n "$ancestor" ]] || ancestor=/
  done
  target=$(findmnt -rn -T "$ancestor" -o TARGET)
  [[ "$target" == "$export_mount" ]] || {
    printf 'The export filesystem mount is not available\n' >&2
    return 1
  }
}
require_mounts

calibredb_ready=false
for _ in $(seq 1 60); do
  if docker exec "$calibre_container" sh -c \
    'command -v calibre-debug >/dev/null && command -v ebook-convert >/dev/null'; then
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

private_run=$(mktemp -d /tmp/calibre-kavita-plan.XXXXXX)
chmod 0700 "$private_run"
manifest_before=$private_run/registered-before.json
manifest_after=$private_run/registered-after.json
raw_manifest=$private_run/unregistered-before.json
raw_after=$private_run/unregistered-after.json
conversion_receipts=$private_run/conversions.json
printf '{"candidates": []}\n' >"$raw_manifest"
if [[ "$include_unregistered" == true ]]; then
  rm -- "$raw_manifest"
  "$import_planner" "$source_path" --manifest "$raw_manifest" >"$private_run/planner-before-report.json"
fi
container_work=$(docker exec --user "$calibre_uid:$calibre_gid" "$calibre_container" mktemp -d /tmp/kavita-export.XXXXXX)
[[ "$container_work" =~ ^/tmp/kavita-export\.[[:alnum:]]+$ ]] || {
  container_work=
  printf 'Calibre returned an invalid staging directory\n' >&2
  exit 1
}
container_stage=$container_work/books
native_wrapper=$container_work/calibredb-preserve-trash.py
docker exec --user "$calibre_uid:$calibre_gid" "$calibre_container" mkdir -- "$container_stage"
# The library-opening CLI normally expires trash even on list/export. This
# ephemeral process-local override preserves source files without changing prefs.
docker exec --user "$calibre_uid:$calibre_gid" -i "$calibre_container" \
  python3 -c 'import pathlib,sys; pathlib.Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())' \
  "$native_wrapper" <<'NATIVE_CLI'
import sys
from calibre.constants import __version__
if __version__.split('.')[:2] != ['9', '16']:
    raise RuntimeError('Calibre version needs preservation verification')
from calibre.db.backend import DB
DB.expire_old_trash = lambda *args, **kwargs: None
from calibre.db.cli.main import main
raise SystemExit(main(['calibredb', *sys.argv[1:]]))
NATIVE_CLI
manifest_fields=uuid,title,authors,series,series_index,formats,last_modified
docker exec --user "$calibre_uid:$calibre_gid" \
  --env "CALIBRE_CONFIG_DIRECTORY=$container_work/config" "$calibre_container" \
  calibre-debug -e "$native_wrapper" -- list --with-library /books --for-machine --fields "$manifest_fields" >"$manifest_before"
docker exec --user "$calibre_uid:$calibre_gid" \
  --env "CALIBRE_CONFIG_DIRECTORY=$container_work/config" "$calibre_container" \
  calibre-debug -e "$native_wrapper" -- export --all --with-library /books \
  --to-dir "$container_stage" \
  --template "$export_template" \
  --dont-save-cover \
  --dont-write-opf
if [[ "$include_unregistered" == true ]]; then
  runuser -u "$export_user" -- mkdir -- "$stage_dir/Uncataloged"
  python3 - "$raw_manifest" "$source_path" "$stage_dir/Uncataloged" <<'COPY_UNREGISTERED'
import hashlib
import json
from pathlib import Path
import re
import sys

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

try:
    plan = json.loads(Path(sys.argv[1]).read_text())
    library = Path(sys.argv[2]).resolve(strict=True)
    target = Path(sys.argv[3])
    candidates = plan['candidates']
    if (plan.get('kind') != 'calibre-catalog-import-plan' or plan.get('version') != 1
            or plan.get('libraryPath') != str(library) or not isinstance(candidates, list)
            or plan.get('counts', {}).get('candidateBooks') != len(candidates)):
        raise ValueError()
    seen = set()
    for record in candidates:
        source = Path(record['path'])
        checksum = record['sha256']
        if (not isinstance(checksum, str) or not re.fullmatch('[0-9a-f]{64}', checksum)
                or checksum in seen or record.get('format') != 'EPUB' or source.suffix.lower() != '.epub'
                or not source.is_absolute() or source.resolve(strict=True) != source):
            raise ValueError()
        source.relative_to(library)
        seen.add(checksum)
        if digest(source) != checksum:
            raise ValueError()
        output = target / ('uncataloged-' + checksum + '.epub')
        with source.open('rb') as incoming, output.open('xb') as outgoing:
            while block := incoming.read(1024 * 1024):
                outgoing.write(block)
        if digest(source) != checksum or digest(output) != checksum:
            raise ValueError()
        output.chmod(0o644)
except (OSError, ValueError, KeyError, TypeError, AttributeError):
    raise SystemExit('Unregistered EPUB manifest or source integrity failed; export was not published') from None
print(f'Copied {len(candidates)} confirmed unregistered EPUBs without importing')
COPY_UNREGISTERED
  tar -C "$stage_dir" -cf - Uncataloged |
    docker exec -i "$calibre_container" tar -C "$container_stage" -xf -
  runuser -u "$export_user" -- rm -rf -- "$stage_dir/Uncataloged"
fi
docker exec --user "$calibre_uid:$calibre_gid" -i "$calibre_container" bash -s -- "$container_stage" <<'CONVERT'
set -euo pipefail
# Prefer the original EPUB, then AZW3, then MOBI, independent of filesystem order.
for format in azw3 mobi; do
  while IFS= read -r -d '' source; do
    target=${source%.*}.epub
    native_epub=false
    for existing in "${source%.*}".[eE][pP][uU][bB]; do
      if [[ -f "$existing" ]]; then native_epub=true; break; fi
    done
    if [[ "$native_epub" == false ]]; then
      if ! ebook-convert "$source" "$target" >/dev/null 2>&1; then
        printf 'Export format conversion failed; export was not published\n' >&2
        exit 1
      fi
    fi
    rm -f -- "$source"
  done < <(find "$1" -type f -iname "*.$format" -print0 | sort -z)
done
CONVERT

# Normalize only staged copies with unsupported declared package versions. A
# receipt binds any permitted byte change to its original and resulting hash.
docker exec --user "$calibre_uid:$calibre_gid" -i "$calibre_container" \
  python3 - "$container_stage" "$normalize_legacy" >"$conversion_receipts" <<'NORMALIZE'
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def version(path):
    with zipfile.ZipFile(path) as archive:
        container = ET.fromstring(archive.read('META-INF/container.xml'))
        package = next(node.attrib['full-path'] for node in container.iter() if node.tag.rsplit('}', 1)[-1] == 'rootfile')
        return ET.fromstring(archive.read(package)).attrib.get('version', '')

root, enabled = Path(sys.argv[1]), sys.argv[2] == 'true'
receipts = {}
try:
    for path in sorted(root.rglob('*')):
        if path.suffix.lower() != '.epub' or not path.is_file():
            continue
        if version(path).split('.')[0] in ('2', '3'):
            continue
        if not enabled:
            raise SystemExit('Unsupported EPUB package version; enable CALIBRE_NORMALIZE_LEGACY_EPUBS for export copies only')
        original = digest(path)
        with tempfile.TemporaryDirectory(prefix='.kavita-normalize.', dir=path.parent) as temporary:
            normalized = Path(temporary) / 'normalized.epub'
            subprocess.run(['ebook-convert', str(path), str(normalized), '--epub-version', '2'],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if version(normalized).split('.')[0] != '2':
                raise ValueError()
            normalized.replace(path)
        receipts[str(path.relative_to(root))] = {'before': original, 'after': digest(path)}
except (OSError, ValueError, KeyError, StopIteration, ET.ParseError, zipfile.BadZipFile, subprocess.CalledProcessError):
    raise SystemExit('Export EPUB inspection or normalization failed; export was not published') from None
print(json.dumps(receipts, sort_keys=True))
NORMALIZE

docker exec "$calibre_container" tar -C "$container_stage" -cf - . |
  runuser -u "$export_user" -- tar -C "$stage_dir" -xf -
docker exec --user "$calibre_uid:$calibre_gid" \
  --env "CALIBRE_CONFIG_DIRECTORY=$container_work/config" "$calibre_container" \
  calibre-debug -e "$native_wrapper" -- list --with-library /books --for-machine --fields "$manifest_fields" >"$manifest_after"
if [[ "$include_unregistered" == true ]]; then
  "$import_planner" "$source_path" --manifest "$raw_after" >"$private_run/planner-after-report.json"
  python3 - "$raw_manifest" "$raw_after" <<'COMPARE_PLANS'
import json
from pathlib import Path
import sys
try:
    before, after = (json.loads(Path(path).read_text()) for path in sys.argv[1:])
    if before != after:
        raise ValueError()
except (OSError, ValueError, TypeError):
    raise SystemExit('Calibre source inventory changed during raw export; export was not published') from None
COMPARE_PLANS
fi
python3 - "$manifest_before" "$manifest_after" "$stage_dir" "$raw_manifest" "$conversion_receipts" <<'VALIDATE'
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

def fail(message):
    raise SystemExit(message)

def inventory(path):
    try:
        rows = json.loads(Path(path).read_text())
        if not isinstance(rows, list) or not rows:
            fail('Calibre registered inventory is empty or invalid; export was not published')
        result = {}
        for row in rows:
            identifier = row.get('id')
            if type(identifier) is not int or identifier <= 0 or identifier in result:
                fail('Calibre registered IDs are invalid; export was not published')
            result[identifier] = row
        return result
    except (OSError, ValueError, TypeError, AttributeError):
        fail('Calibre registered inventory is unreadable; export was not published')

before, after = inventory(sys.argv[1]), inventory(sys.argv[2])
if before != after:
    fail('Calibre changed during export; export was not published')
represented = set()
try:
    candidates = json.loads(Path(sys.argv[4]).read_text())['candidates']
    receipts = json.loads(Path(sys.argv[5]).read_text())
    expected_raw = {row['sha256']: row for row in candidates}
except (OSError, ValueError, TypeError, KeyError):
    fail('Raw EPUB validation inventory is unreadable; export was not published')
raw_represented = set()
def digest(path):
    try:
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    except OSError:
        fail('Source or export verification could not read a book; export was not published')

for path in Path(sys.argv[3]).rglob('*'):
    if not path.is_file() or path.suffix.lower() not in ('.epub', '.pdf'):
        continue
    relative = path.relative_to(sys.argv[3]).as_posix()
    if relative.startswith('Uncataloged/uncataloged-'):
        match = re.fullmatch(r'uncataloged-([0-9a-f]{64})\.epub', path.name)
        if not match or match[1] not in expected_raw or match[1] in raw_represented:
            fail('Exported raw EPUB hash set differs from its manifest; export was not published')
        checksum = match[1]
        record = expected_raw[checksum]
        receipt = receipts.get(relative)
        expected_output = checksum
        if receipt:
            if receipt.get('before') != checksum:
                fail('Normalized raw EPUB receipt is invalid; export was not published')
            expected_output = receipt.get('after')
        if digest(path) != expected_output or digest(Path(record['path'])) != checksum:
            fail('Unregistered source or exported EPUB changed; export was not published')
        raw_represented.add(checksum)
    else:
        match = re.search(r' - ([0-9]+)\.(epub|pdf)$', path.name, re.I)
        if not match:
            fail('Export paths do not contain the expected registered IDs; export was not published')
        represented.add(int(match[1]))
    try:
        if path.suffix.lower() == '.epub':
            with zipfile.ZipFile(path) as archive:
                if archive.testzip() is not None or archive.read('mimetype').strip() != b'application/epub+zip':
                    fail('Exported EPUB integrity failed; export was not published')
        elif path.open('rb').read(5) != b'%PDF-':
            fail('Exported PDF signature failed; export was not published')
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, RuntimeError):
        fail('Exported book is unreadable; export was not published')
if represented != set(before):
    fail('Exported registered IDs or book count differ from Calibre; export was not published')
if raw_represented != set(expected_raw):
    fail('Exported raw EPUB count differs from its manifest; export was not published')
print(f'Validated export for {len(represented)} registered books and {len(raw_represented)} unregistered EPUBs')
VALIDATE
require_mounts
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
