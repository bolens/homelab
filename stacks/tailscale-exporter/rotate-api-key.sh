#!/usr/bin/env bash
set -euo pipefail

_stack_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_env_file="${TAILSCALE_EXPORTER_ENV_FILE:-${_stack_dir}/stack.env}"
_headscale_container="${HEADSCALE_CONTAINER:-headscale}"
_exporter_container="${TAILSCALE_EXPORTER_CONTAINER:-tailscale-exporter}"
_expiration="${HEADSCALE_API_KEY_EXPIRATION:-365d}"

for _command in docker jq mktemp; do
  command -v "$_command" >/dev/null 2>&1 || {
    printf 'ERROR: required command is unavailable: %s\n' "$_command" >&2
    exit 1
  }
done

[[ -f "$_env_file" ]] || {
  printf 'ERROR: runtime environment file not found: %s\n' "$_env_file" >&2
  exit 1
}

umask 077
_old_file="$(mktemp "${_env_file}.old.XXXXXX")"
_new_file="$(mktemp "${_env_file}.new.XXXXXX")"
_new_key=''

cleanup() {
  _new_key=''
  rm -f -- "$_old_file" "$_new_file"
}
trap cleanup EXIT

cp --preserve=mode,ownership -- "$_env_file" "$_old_file"

_old_key=''
while IFS= read -r _line || [[ -n "$_line" ]]; do
  case "$_line" in
    HEADSCALE_API_KEY=*) _old_key="${_line#*=}" ;;
  esac
done <"$_old_file"

# Headscale lists only masked prefixes. Match the prior exporter key locally;
# neither the old nor new credential is written to stdout or command arguments.
_old_prefix=''
while IFS= read -r _prefix; do
  _prefix_base="${_prefix%\*\*\*}"
  if [[ -n "$_old_key" && "$_old_key" == "${_prefix_base}"* ]]; then
    _old_prefix="$_prefix_base"
    break
  fi
done < <(docker exec "$_headscale_container" \
  headscale apikeys list -o json | jq -r '.[].prefix')

_new_key="$(docker exec "$_headscale_container" \
  headscale apikeys create --expiration "$_expiration")"
[[ "$_new_key" == hskey-api-* ]] || {
  printf 'ERROR: Headscale did not return an API key\n' >&2
  exit 1
}

_found=false
while IFS= read -r _line || [[ -n "$_line" ]]; do
  case "$_line" in
    HEADSCALE_API_KEY=*)
      printf 'HEADSCALE_API_KEY=%s\n' "$_new_key" >>"$_new_file"
      _found=true
      ;;
    *) printf '%s\n' "$_line" >>"$_new_file" ;;
  esac
done <"$_old_file"
[[ "$_found" == true ]] || printf '\nHEADSCALE_API_KEY=%s\n' "$_new_key" >>"$_new_file"

chmod --reference="$_env_file" "$_new_file"
chown --reference="$_env_file" "$_new_file"
mv -f -- "$_new_file" "$_env_file"

if ! docker compose \
  --project-directory "$_stack_dir" \
  --env-file "$_env_file" \
  -f "${_stack_dir}/docker-compose.yml" \
  up -d --no-deps --force-recreate tailscale-exporter; then
  mv -f -- "$_old_file" "$_env_file"
  docker compose --project-directory "$_stack_dir" --env-file "$_env_file" \
    -f "${_stack_dir}/docker-compose.yml" up -d --no-deps --force-recreate \
    tailscale-exporter >/dev/null
  printf 'ERROR: exporter recreation failed; prior environment restored\n' >&2
  exit 1
fi

sleep "${TAILSCALE_EXPORTER_VERIFY_DELAY:-20}"
if docker logs --since 2m "$_exporter_container" 2>&1 \
  | grep -qiE 'Unauthenticated|invalid token|collector failed|level=ERROR'; then
  mv -f -- "$_old_file" "$_env_file"
  docker compose --project-directory "$_stack_dir" --env-file "$_env_file" \
    -f "${_stack_dir}/docker-compose.yml" up -d --no-deps --force-recreate \
    tailscale-exporter >/dev/null
  printf 'ERROR: authentication check failed; prior environment restored\n' >&2
  exit 1
fi

if [[ -n "$_old_prefix" ]]; then
  docker exec "$_headscale_container" \
    headscale apikeys expire --prefix "$_old_prefix" >/dev/null
fi

_new_key=''
printf 'Headscale exporter API key rotated and verified successfully.\n'
