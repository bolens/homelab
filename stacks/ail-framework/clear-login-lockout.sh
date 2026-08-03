#!/usr/bin/env bash
# Clear AIL Redis_Cache brute-force counters (failed_login_ip:* / failed_login_user_id:*).
# Run from repo host when the UI says "Max Connection Attempts reached".
set -euo pipefail
CONTAINER="${1:-ail-framework}"
docker exec "$CONTAINER" bash -c '
  CLI=/opt/AIL/redis/src/redis-cli
  for k in $($CLI -p 6379 KEYS "failed_login_*"); do
    $CLI -p 6379 DEL "$k"
  done
'
echo "Cleared failed_login_* keys in Redis_Cache (port 6379) on $CONTAINER."
