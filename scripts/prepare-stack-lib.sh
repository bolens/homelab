#!/usr/bin/env bash
# Shared helpers for stacks/*/prepare-stack.sh — verbose, consistent output.
# Examples: scripts/prepare-stack.examples/standard-self-contained.sh
#           scripts/prepare-stack.examples/standard-with-lib.sh
#
# Sourced with: source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
# Do not run this file directly.

prepare_stack__require_prepdir() {
  if [[ -z "${PREPARE_STACK_DIR:-}" ]]; then
    echo "prepare-stack-lib.sh: PREPARE_STACK_DIR is not set (call prepare_stack_begin first)." >&2
    return 1
  fi
}

prepare_stack_begin() {
  local dir="${1:?stack directory}"
  PREPARE_STACK_DIR="$(cd "$dir" && pwd)" || return 1
  cd "$PREPARE_STACK_DIR" || return 1
  PREPARE_STACK_NAME="$(basename "$PREPARE_STACK_DIR")"
  prepare_stack_load_shared_roots
  echo "[prepare-stack] ${PREPARE_STACK_NAME}: starting..."
}

prepare_stack_msg() {
  prepare_stack__require_prepdir || return 1
  echo "[prepare-stack] ${PREPARE_STACK_NAME}: $*"
}

# Read only portable host-root values from the repository's optional shared.env.
# This deliberately does not source the file, so arbitrary shell content is
# never executed. Already-exported values take precedence.
prepare_stack_load_shared_roots() {
  local shared_file="$PREPARE_STACK_DIR/../../shared.env"
  [[ -f "$shared_file" ]] || return 0
  local var_name current line value
  for var_name in MEDIA_ROOT LAB_ROOT; do
    current="${!var_name:-}"
    [[ -z "$current" ]] || continue
    line=$(grep -E "^${var_name}=" "$shared_file" 2>/dev/null | tail -1) || true
    [[ -n "$line" ]] || continue
    value="${line#*=}"
    value="${value%$'\r'}"
    value="${value#\"}"; value="${value%\"}"
    value="${value#\'}"; value="${value%\'}"
    value="$(prepare_stack__expand_home_in_path "$value")"
    [[ -n "$value" ]] || continue
    printf -v "$var_name" '%s' "$value"
    export "${var_name?}"
  done
}

prepare_stack_copy_env() {
  prepare_stack__require_prepdir || return 1
  if [[ -f stack.env.example ]]; then
    if [[ ! -f stack.env ]]; then
      cp stack.env.example stack.env
      prepare_stack_msg "created stack.env from stack.env.example — set secrets and review variables before docker compose up."
    else
      prepare_stack_msg "stack.env already exists (left unchanged)."
    fi
  else
    prepare_stack_msg "no stack.env.example found (skipped)."
  fi
}

# Expand ${HOME} and leading ~ in paths read from stack.env (compose does this when reading .env).
prepare_stack__expand_home_in_path() {
  local p="${1:-}"
  p="${p//\$\{HOME\}/${HOME:-}}"
  if [[ "${p:0:1}" == '~' ]]; then
    p="${HOME:-}${p:1}"
  fi
  printf '%s' "$p"
}

# Ensure a host directory exists; path from stack.env (VAR=...) or default_path.
# Strips optional surrounding quotes on the value. Safe to re-run.
prepare_stack_ensure_dir_from_env() {
  prepare_stack__require_prepdir || return 1
  local var_name="${1:?variable name}"
  local default_path="${2:?default directory}"
  local dir="$default_path"
  if [[ -f stack.env ]]; then
    local line val
    line=$(grep -E "^${var_name}=" stack.env 2>/dev/null | tail -1) || true
    if [[ -n "${line}" ]]; then
      val="${line#*=}"
      val="${val%$'\r'}"
      val="${val#\"}"
      val="${val%\"}"
      val="${val#\'}"
      val="${val%\'}"
      [[ -n "$val" ]] && dir="$val"
    fi
  fi
  dir="$(prepare_stack__expand_home_in_path "$dir")"
  mkdir -p "$dir"
  prepare_stack_msg "ensured $var_name → $dir"
}

# Copy an example to a path configured in stack.env. Existing files are never
# overwritten. Useful for stacks that bind-mount application config outside the
# repository (normally under ${XDG_CONFIG_HOME:-$HOME/.config}).
prepare_stack_copy_example_to_env_path() {
  prepare_stack__require_prepdir || return 1
  local var_name="${1:?variable name}"
  local default_path="${2:?default path}"
  local example="${3:?example file}"
  local destination="$default_path"
  if [[ -f stack.env ]]; then
    local line val
    line=$(grep -E "^${var_name}=" stack.env 2>/dev/null | tail -1) || true
    if [[ -n "$line" ]]; then
      val="${line#*=}"
      val="${val%$'\r'}"
      val="${val#\"}"; val="${val%\"}"
      val="${val#\'}"; val="${val%\'}"
      [[ -n "$val" ]] && destination="$val"
    fi
  fi
  destination="$(prepare_stack__expand_home_in_path "$destination")"
  mkdir -p "$(dirname "$destination")"
  if [[ -f "$destination" ]]; then
    prepare_stack_msg "$var_name target $destination already exists (left unchanged)."
  elif [[ -f "$example" ]]; then
    cp "$example" "$destination"
    prepare_stack_msg "created $destination from $(basename "$example") — review before deployment."
  else
    prepare_stack_msg "example $example is missing; could not prepare $var_name."
    return 1
  fi
}

prepare_stack_copy_caddy() {
  prepare_stack__require_prepdir || return 1
  if [[ -f caddy_snippet.conf.example ]]; then
    if [[ ! -f caddy_snippet.conf ]]; then
      cp caddy_snippet.conf.example caddy_snippet.conf
      prepare_stack_msg "created caddy_snippet.conf — replace placeholder hostname with yours; reload Caddy after changes."
    else
      prepare_stack_msg "caddy_snippet.conf already exists (left unchanged)."
    fi
  else
    prepare_stack_msg "no caddy_snippet.conf.example (skipped)."
  fi
}

# Ensure a Docker network exists (idempotent). Use for compose files that declare
#   networks: { monitor: { external: true } }
# Skips if docker is missing or the daemon is not reachable (e.g. CI copy-only).
# Docker Compose reads `.env` in the stack directory for ${VAR} interpolation in the YAML.
# Copy stack.env -> .env (no symlink) so `docker compose up -d` works without --env-file stack.env.
# Re-run ./prepare-stack.sh after editing stack.env so .env stays in sync.
prepare_stack_sync_dotenv_from_stack_env() {
  prepare_stack__require_prepdir || return 1
  if [[ ! -f stack.env ]]; then
    return 0
  fi
  if [[ -L .env ]]; then
    rm -f .env
  fi
  cp -f stack.env .env
  prepare_stack_msg "copied stack.env -> .env for Compose default env file (interpolation + same values as stack.env)."
}

prepare_stack_ensure_docker_network() {
  prepare_stack__require_prepdir || return 1
  local net="${1:?network name}"
  local internal="${2:-false}"
  if ! command -v docker >/dev/null 2>&1; then
    prepare_stack_msg "docker not in PATH; skipped creating network '$net'."
    return 0
  fi
  if ! docker info >/dev/null 2>&1; then
    prepare_stack_msg "Docker daemon not reachable; skipped creating network '$net'."
    return 0
  fi
  if docker network inspect "$net" >/dev/null 2>&1; then
    prepare_stack_msg "docker network '$net' already exists."
  elif [[ "$internal" == "true" ]]; then
    docker network create --internal "$net"
    prepare_stack_msg "created internal docker network '$net'."
  else
    docker network create "$net"
    prepare_stack_msg "created docker network '$net'."
  fi
}

prepare_stack_ensure_docker_volume() {
  prepare_stack__require_prepdir || return 1
  local volume="${1:?volume name}"
  if ! command -v docker >/dev/null 2>&1; then
    prepare_stack_msg "docker not in PATH; skipped creating volume '$volume'."
    return 0
  fi
  if ! docker info >/dev/null 2>&1; then
    prepare_stack_msg "Docker daemon not reachable; skipped creating volume '$volume'."
    return 0
  fi
  if docker volume inspect "$volume" >/dev/null 2>&1; then
    prepare_stack_msg "docker volume '$volume' already exists."
  else
    docker volume create "$volume" >/dev/null
    prepare_stack_msg "created docker volume '$volume'."
  fi
}

prepare_stack_report_review_items() {
  prepare_stack__require_prepdir || return 1
  if [[ -f stack.env ]]; then
    local review_names
    review_names="$(
      awk -F= '
        /^[[:space:]]*#/ || !/^[A-Za-z_][A-Za-z0-9_]*=/ { next }
        {
          value=substr($0, index($0, "=") + 1)
          gsub(/^[[:space:]"\047]+|[[:space:]"\047]+$/, "", value)
          lower=tolower(value)
          if (value == "" || lower ~ /^(change[-_]?me|replace[-_]?me|your[-_])/) {
            print $1
          }
        }
      ' stack.env | paste -sd, -
    )"
    if [[ -n "$review_names" ]]; then
      prepare_stack_msg "review unset or placeholder variables in stack.env: $review_names"
    else
      prepare_stack_msg "stack.env contains no obvious empty or placeholder assignments."
    fi
  fi

  if [[ -f caddy_snippet.conf ]]; then
    if grep -Eqi 'example\.com|yourdomain|change[-_]?me|replace[-_]?me' caddy_snippet.conf; then
      prepare_stack_msg "review placeholder hostname(s) in caddy_snippet.conf."
    else
      prepare_stack_msg "caddy_snippet.conf contains no obvious placeholder hostname."
    fi
  fi
}

prepare_stack_end() {
  prepare_stack__require_prepdir || return 1
  prepare_stack_sync_dotenv_from_stack_env
  prepare_stack_report_review_items
  prepare_stack_msg "done. Next: edit stack.env if needed, re-run ./prepare-stack.sh to refresh .env, then: docker compose up -d"
}
