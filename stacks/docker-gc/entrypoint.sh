#!/bin/bash
# Convert env vars to spotify docker-gc format and run.
set -e

STATE_DIR=${STATE_DIR:-/var/lib/docker-gc}
mkdir -p "$STATE_DIR"
cd "$STATE_DIR"

# Generic true/false -> 1/0 for script vars
to_01() {
  case "${1:-0}" in
    [tT][rR][uU][eE]|1|[yY]|[yY][eE][sS]) echo 1 ;;
    *) echo 0 ;;
  esac
}

# DRY_RUN: spotify expects 0/1; we accept true/false (default true for safety)
export DRY_RUN=$(to_01 "${DRY_RUN:-true}")
export DRY_RUN_CONTAINERS=$(to_01 "${DRY_RUN_CONTAINERS:-$DRY_RUN}")
export DRY_RUN_IMAGES=$(to_01 "${DRY_RUN_IMAGES:-$DRY_RUN}")
export DRY_RUN_VOLUMES=$(to_01 "${DRY_RUN_VOLUMES:-$DRY_RUN}")
export DRY_RUN_NETWORKS=$(to_01 "${DRY_RUN_NETWORKS:-$DRY_RUN}")
export DRY_RUN_BUILD_CACHE=$(to_01 "${DRY_RUN_BUILD_CACHE:-$DRY_RUN}")

# Parse human-readable or seconds into seconds (e.g. 24h, 1d, 3600)
parse_grace() {
  local val="${1:-}"
  local default="${2:-3600}"
  local n
  [ -z "$val" ] && echo "$default" && return
  case "$val" in
    *s) n=${val%s}; echo "${n:-0}" ;;
    *m) n=${val%m}; echo $((${n:-0} * 60)) ;;
    *h) n=${val%h}; echo $((${n:-0} * 3600)) ;;
    *d) n=${val%d}; echo $((${n:-0} * 86400)) ;;
    *) echo "$val" ;;
  esac
}

# Overall grace period (default 3600)
grace_seconds=$(parse_grace "${GRACE_PERIOD_SECONDS:-${GRACE_PERIOD:-}}" 3600)
export GRACE_PERIOD_SECONDS=$grace_seconds

# Per-resource grace periods (default to overall)
grace_containers=$(parse_grace "${GRACE_PERIOD_CONTAINERS:-}" "$grace_seconds")
grace_images=$(parse_grace "${GRACE_PERIOD_IMAGES:-}" "$grace_seconds")
grace_volumes=$(parse_grace "${GRACE_PERIOD_VOLUMES:-}" "$grace_seconds")
grace_networks=$(parse_grace "${GRACE_PERIOD_NETWORKS:-}" "$grace_seconds")
grace_build_cache=$(parse_grace "${GRACE_PERIOD_BUILD_CACHE:-}" "$grace_seconds")

export GRACE_PERIOD_CONTAINERS=$grace_containers
export GRACE_PERIOD_IMAGES=$grace_images
export GRACE_PERIOD_VOLUMES=$grace_volumes
export MINIMUM_IMAGES_TO_SAVE=${MINIMUM_IMAGES_TO_SAVE:-0}

# Removal flags (true/false -> 1/0)
export REMOVE_ASSOCIATED_VOLUME=$(to_01 "${REMOVE_ASSOCIATED_VOLUME:-1}")
export FORCE_CONTAINER_REMOVAL=$(to_01 "${FORCE_CONTAINER_REMOVAL:-0}")
export FORCE_IMAGE_REMOVAL=$(to_01 "${FORCE_IMAGE_REMOVAL:-0}")
export EXCLUDE_DEAD=$(to_01 "${EXCLUDE_DEAD:-0}")
export REMOVE_VOLUMES=$(to_01 "${REMOVE_VOLUMES:-0}")
export LOG_TO_SYSLOG=$(to_01 "${LOG_TO_SYSLOG:-0}")

# EXCLUDE_IMAGES -> EXCLUDE_FROM_GC file (one pattern per line)
EXCLUDE_GC="$STATE_DIR/exclude-images"
if [ -n "${EXCLUDE_IMAGES:-}" ]; then
  echo "$EXCLUDE_IMAGES" | tr ' ' '\n' | grep -v '^$' > "$EXCLUDE_GC"
else
  touch "$EXCLUDE_GC"
fi
export EXCLUDE_FROM_GC="$EXCLUDE_GC"

# EXCLUDE_CONTAINERS -> EXCLUDE_CONTAINERS_FROM_GC file (one name per line)
EXCLUDE_CTR="$STATE_DIR/exclude-containers"
if [ -n "${EXCLUDE_CONTAINERS:-}" ]; then
  echo "$EXCLUDE_CONTAINERS" | tr ' ' '\n' | grep -v '^$' > "$EXCLUDE_CTR"
else
  touch "$EXCLUDE_CTR"
fi
export EXCLUDE_CONTAINERS_FROM_GC="$EXCLUDE_CTR"

# EXCLUDE_VOLUMES -> EXCLUDE_VOLUMES_IDS_FILE (one ID/name per line)
EXCLUDE_VOL="$STATE_DIR/exclude-volumes"
if [ -n "${EXCLUDE_VOLUMES:-}" ]; then
  echo "$EXCLUDE_VOLUMES" | tr ' ' '\n' | grep -v '^$' > "$EXCLUDE_VOL"
  export EXCLUDE_VOLUMES_IDS_FILE="$EXCLUDE_VOL"
else
  export EXCLUDE_VOLUMES_IDS_FILE=${EXCLUDE_VOLUMES_IDS_FILE:-/etc/docker-gc-exclude-volumes}
fi

# Run main docker-gc (containers, images, volumes)
/docker-gc

# --- Network prune (optional) ---
REMOVE_NETWORKS=$(to_01 "${REMOVE_NETWORKS:-0}")
DRY_RUN_NETWORKS=$(to_01 "${DRY_RUN_NETWORKS:-$DRY_RUN}")

if [[ $REMOVE_NETWORKS -gt 0 ]]; then
  DOCKER=${DOCKER:-docker}

  # Build exclude pattern (docker network prune has no exclude; we filter manually)
  EXCLUDE_NET="$STATE_DIR/exclude-networks"
  if [ -n "${EXCLUDE_NETWORKS:-}" ]; then
    echo "$EXCLUDE_NETWORKS" | tr ' ' '\n' | grep -v '^$' > "$EXCLUDE_NET"
  else
    touch "$EXCLUDE_NET"
  fi

  # Get unused networks older than grace period, excluding by name
  $DOCKER network ls --format '{{.ID}} {{.Name}}' 2>/dev/null | while read -r nwid nwname; do
    [ -z "$nwid" ] && continue
    # Skip default networks (Docker never prunes these, but we filter for consistency)
    case "$nwname" in bridge|host|none) continue ;; esac
    # Skip excluded names
    grep -qFx "$nwname" "$EXCLUDE_NET" 2>/dev/null && continue
    # Skip if in use
    cnt=$($DOCKER network inspect -f '{{len .Containers}}' "$nwid" 2>/dev/null || echo 1)
    [ "$cnt" != "0" ] && continue
    # Check age
    created=$($DOCKER network inspect -f '{{.Created}}' "$nwid" 2>/dev/null)
    [ -z "$created" ] && continue
    if date --utc >/dev/null 2>&1; then
      epoch=$(date -u -d "$created" "+%s" 2>/dev/null)
    else
      epoch=$(date -j -u -f "%Y-%m-%dT%H:%M:%S" "${created:0:19}" "+%s" 2>/dev/null)
    fi
    [ -z "$epoch" ] && continue
    now=$(date -u "+%s")
    [ $((now - epoch)) -lt $grace_networks ] && continue
    echo "$nwid $nwname"
  done > networks.reap 2>/dev/null || true

  if [ -s networks.reap ]; then
    while read -r nwid nwname; do
      [ -z "$nwid" ] && continue
      if [[ $DRY_RUN_NETWORKS -gt 0 ]]; then
        echo "[$(date +'%Y-%m-%dT%H:%M:%S')] [INFO] : The following network would have been removed: $nwid $nwname"
      else
        $DOCKER network rm "$nwid" 2>/dev/null && echo "[$(date +'%Y-%m-%dT%H:%M:%S')] [INFO] : Removed network $nwid $nwname" || true
      fi
    done < networks.reap
  fi
fi

# --- Build cache prune (optional) ---
REMOVE_BUILD_CACHE=$(to_01 "${REMOVE_BUILD_CACHE:-0}")
DRY_RUN_BUILD_CACHE=$(to_01 "${DRY_RUN_BUILD_CACHE:-$DRY_RUN}")

if [[ $REMOVE_BUILD_CACHE -gt 0 ]]; then
  DOCKER=${DOCKER:-docker}
  gp=$grace_build_cache
  if [[ $gp -ge 86400 ]]; then
    UNTIL="$((gp / 86400))d"
  elif [[ $gp -ge 3600 ]]; then
    UNTIL="$((gp / 3600))h"
  else
    UNTIL="${gp}s"
  fi

  if [[ $DRY_RUN_BUILD_CACHE -gt 0 ]]; then
    echo "[$(date +'%Y-%m-%dT%H:%M:%S')] [INFO] : Would run: docker builder prune -f --filter until=$UNTIL"
  else
    $DOCKER builder prune -f --filter "until=$UNTIL" 2>/dev/null || true
  fi
fi
