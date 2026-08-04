#!/usr/bin/env bash
# Copy upstream PostHog hobby compose files, seed compose/ + GeoIP, env, Caddy, monitor network.
# Optional: ./prepare-stack.sh --clone  (or PREPARE_STACK_CLONE=1) runs ./clone-repo.sh first.
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"

if [[ "${1:-}" == "--clone" ]] || [[ "${PREPARE_STACK_CLONE:-0}" == "1" ]]; then
  "$_PREPDIR/clone-repo.sh"
fi

if [[ ! -d "$_PREPDIR/posthog/docker" ]]; then
  echo "[prepare-stack] posthog/: missing or incomplete. Run ./clone-repo.sh or: ./prepare-stack.sh --clone" >&2
  exit 1
fi

prepare_stack_msg "copying docker-compose.base.yml, docker-compose.hobby.yml, .env.services from posthog/"
cp "$_PREPDIR/posthog/docker-compose.base.yml" "$_PREPDIR/docker-compose.base.yml"
cp "$_PREPDIR/posthog/docker-compose.hobby.yml" "$_PREPDIR/docker-compose.hobby.yml"
cp "$_PREPDIR/posthog/.env.services" "$_PREPDIR/.env.services"

prepare_stack_msg "writing compose/ entrypoints (same layout as upstream deploy-hobby)"
rm -rf "$_PREPDIR/compose"
mkdir -p "$_PREPDIR/compose"
cat >"$_PREPDIR/compose/start" <<'EOF'
#!/bin/bash
./compose/wait
./bin/migrate
./bin/docker-server
EOF
chmod 0755 "$_PREPDIR/compose/start"
cat >"$_PREPDIR/compose/temporal-django-worker" <<'EOF'
#!/bin/bash
./bin/temporal-django-worker
EOF
chmod 0755 "$_PREPDIR/compose/temporal-django-worker"
cat >"$_PREPDIR/compose/wait" <<'EOF'
#!/usr/bin/env python3

import socket
import time

def loop():
    print("Waiting for ClickHouse and Postgres to be ready")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('clickhouse', 9000))
        print("Clickhouse is ready")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('db', 5432))
        print("Postgres is ready")
    except ConnectionRefusedError:
        time.sleep(5)
        loop()

loop()
EOF
chmod 0755 "$_PREPDIR/compose/wait"

mkdir -p "$_PREPDIR/share"
if [[ ! -f "$_PREPDIR/share/GeoLite2-City.mmdb" ]]; then
  if command -v brotli >/dev/null 2>&1 && command -v curl >/dev/null 2>&1; then
    prepare_stack_msg "downloading GeoLite2-City.mmdb (PostHog / feature-flags) ..."
    curl -fsSL 'https://mmdbcdn.posthog.net/' --http1.1 | brotli --decompress >"$_PREPDIR/share/GeoLite2-City.mmdb"
    printf '{"date":"%s"}\n' "$(date +%Y-%m-%d)" >"$_PREPDIR/share/GeoLite2-City.json"
    chmod 0644 "$_PREPDIR/share/GeoLite2-City.mmdb" "$_PREPDIR/share/GeoLite2-City.json" || true
  else
    prepare_stack_msg "skipping GeoIP download (install curl and brotli, or add share/GeoLite2-City.mmdb manually — see README)."
  fi
else
  prepare_stack_msg "share/GeoLite2-City.mmdb already present."
fi

prepare_stack_copy_env

# Auto-fill secrets when placeholders remain (matches upstream installer behaviour).
if [[ -f "$_PREPDIR/stack.env" ]]; then
  if grep -q '^POSTHOG_SECRET=REPLACE_POSTHOG_SECRET$' "$_PREPDIR/stack.env"; then
    PH_POSTHOG_SECRET="$(openssl rand -hex 28)"
    sed -i "s|^POSTHOG_SECRET=REPLACE_POSTHOG_SECRET\$|POSTHOG_SECRET=${PH_POSTHOG_SECRET}|" "$_PREPDIR/stack.env"
    prepare_stack_msg "generated POSTHOG_SECRET in stack.env (was REPLACE_POSTHOG_SECRET)."
  fi
  if grep -q '^ENCRYPTION_SALT_KEYS=REPLACE_ENCRYPTION_SALT_KEYS$' "$_PREPDIR/stack.env"; then
    PH_ENC_SALT="$(openssl rand -hex 16)"
    sed -i "s|^ENCRYPTION_SALT_KEYS=REPLACE_ENCRYPTION_SALT_KEYS\$|ENCRYPTION_SALT_KEYS=${PH_ENC_SALT}|" "$_PREPDIR/stack.env"
    prepare_stack_msg "generated ENCRYPTION_SALT_KEYS in stack.env (was REPLACE_ENCRYPTION_SALT_KEYS)."
  fi
  cp "$_PREPDIR/stack.env" "$_PREPDIR/.env"
  prepare_stack_msg "copied stack.env -> .env for PostHog compose."
fi

prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "monitor"
prepare_stack_msg "done. Set DOMAIN in stack.env if still a placeholder, then: docker compose up -d --pull always"
prepare_stack_msg "first boot often needs 10+ minutes; check: curl -sS -o /dev/null -w '%{http_code}\\n' https://YOUR_DOMAIN/_health"
prepare_stack_end
