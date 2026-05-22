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
  PREPARE_STACK_DIR="$(cd "$dir" && pwd)"
  cd "$PREPARE_STACK_DIR"
  PREPARE_STACK_NAME="$(basename "$PREPARE_STACK_DIR")"
  echo "[prepare-stack] ${PREPARE_STACK_NAME}: starting..."
}

prepare_stack_msg() {
  prepare_stack__require_prepdir || return 1
  echo "[prepare-stack] ${PREPARE_STACK_NAME}: $*"
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
  else
    docker network create "$net"
    prepare_stack_msg "created docker network '$net'."
  fi
}

prepare_stack_end() {
  prepare_stack__require_prepdir || return 1
  prepare_stack_sync_dotenv_from_stack_env
  prepare_stack_msg "done. Next: edit stack.env if needed, re-run ./prepare-stack.sh to refresh .env, then: docker compose up -d"
}
