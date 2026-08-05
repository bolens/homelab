#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_ensure_docker_network "ingress-admin"

if [[ ! -f "$_PREPDIR/docker-compose.override.yml" ]]; then
  cp "$_PREPDIR/docker-compose.override.yml.example" "$_PREPDIR/docker-compose.override.yml"
  prepare_stack_msg "created docker-compose.override.yml from example — adjust bind mounts and caddy network."
else
  prepare_stack_msg "docker-compose.override.yml already exists (left unchanged)."
fi

prepare_stack_copy_caddy

# Harbor's proxy runs as nginx UID 10000. Upstream `prepare` can regenerate this
# file as host-only 0640, so preserve host ownership while granting nginx read.
_HARBOR_NGINX_CONFIG="$_PREPDIR/harbor/common/config/nginx/nginx.conf"
if [[ -f "$_HARBOR_NGINX_CONFIG" ]] && command -v setfacl >/dev/null 2>&1; then
  setfacl -m u:10000:r "$_HARBOR_NGINX_CONFIG"
  prepare_stack_msg "granted Harbor nginx UID 10000 read access to generated nginx.conf."
fi

prepare_stack_end
