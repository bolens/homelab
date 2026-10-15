#!/usr/bin/env bash
# Builder cache only. Never chain to generic container/image/volume GC.
set -euo pipefail

DOCKER=${DOCKER:-docker}
builder=${BUILDER_CACHE_BUILDER:-default}
maximum=${BUILDER_CACHE_MAX_GIB:-20}
minimum=${BUILDER_CACHE_MIN_FREE_GIB:-40}
reserved=${BUILDER_CACHE_RESERVED_GIB:-4}
age=${BUILDER_CACHE_MIN_AGE_HOURS:-168}
dry_run=${BUILDER_CACHE_DRY_RUN:-true}

refuse() { echo "Builder-cache configuration or CLI support unavailable." >&2; exit 2; }
[[ $builder =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$ ]] || refuse
for value in "$maximum" "$minimum" "$reserved"; do
  [[ $value =~ ^[1-9][0-9]{0,3}$ ]] || refuse
  (( value <= 4096 )) || refuse
done
(( reserved < maximum )) || refuse
[[ $age =~ ^[1-9][0-9]{0,3}$ ]] || refuse
(( age >= 24 && age <= 8760 )) || refuse
case "$dry_run" in
  true|1) dry_run=true ;;
  false|0) dry_run=false ;;
  *) refuse ;;
esac

# Local flag support is necessary; unsupported daemon capabilities still fail
# normally at prune time. Never substitute an older/broader prune command.
help=$("$DOCKER" buildx prune --help) || refuse
for flag in --max-used-space --min-free-space --reserved-space; do
  [[ $help == *"$flag"* ]] || refuse
done
args=(buildx --builder "$builder" prune --force
      --filter 'private=""' --filter "until=${age}h"
      --max-used-space "${maximum}GiB" --min-free-space "${minimum}GiB"
      --reserved-space "${reserved}GiB")
if [[ $dry_run == true ]]; then
  printf 'DRY RUN: '; printf '%q ' "$DOCKER" "${args[@]}"; printf '\n'
else
  "$DOCKER" "${args[@]}"
  echo 'Builder-cache prune completed; capacity targets are best effort, not a filesystem quota.'
fi
