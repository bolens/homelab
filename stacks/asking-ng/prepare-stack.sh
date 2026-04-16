#!/usr/bin/env bash
# Prepare local files before first deploy. Safe to re-run: existing stack.env and caddy_snippet.conf are not overwritten.
# Self-contained (no homelab monorepo scripts/) so this repo can be cloned standalone.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
STACK_NAME="$(basename "$SCRIPT_DIR")"

echo "[prepare-stack] ${STACK_NAME}: starting..."

if [[ -f stack.env.example ]]; then
  if [[ ! -f stack.env ]]; then
    cp stack.env.example stack.env
    echo "[prepare-stack] ${STACK_NAME}: created stack.env from stack.env.example — set secrets and review variables before docker compose up."
  else
    echo "[prepare-stack] ${STACK_NAME}: stack.env already exists (left unchanged)."
  fi
else
  echo "[prepare-stack] ${STACK_NAME}: no stack.env.example found (skipped)."
fi

if [[ -f stack.env.dev.example ]]; then
  if [[ ! -f stack.env.dev ]]; then
    cp stack.env.dev.example stack.env.dev
    echo "[prepare-stack] ${STACK_NAME}: created stack.env.dev from stack.env.dev.example (optional script/dev overrides)."
  else
    echo "[prepare-stack] ${STACK_NAME}: stack.env.dev already exists (left unchanged)."
  fi
else
  echo "[prepare-stack] ${STACK_NAME}: no stack.env.dev.example found (skipped)."
fi

if [[ -f scripts/sync-caddy-snippets.sh ]]; then
  bash scripts/sync-caddy-snippets.sh
  echo "[prepare-stack] ${STACK_NAME}: synced caddy snippet templates."
elif [[ -f caddy_snippet.conf.example ]]; then
  if [[ ! -f caddy_snippet.conf ]]; then
    cp caddy_snippet.conf.example caddy_snippet.conf
    echo "[prepare-stack] ${STACK_NAME}: created caddy_snippet.conf — replace placeholder hostname with yours; reload Caddy after changes."
  else
    echo "[prepare-stack] ${STACK_NAME}: caddy_snippet.conf already exists (left unchanged)."
  fi
else
  echo "[prepare-stack] ${STACK_NAME}: no caddy_snippet.conf.example (skipped)."
fi

ensure_docker_network() {
  local net="${1:?network name}"
  if ! command -v docker >/dev/null 2>&1; then
    echo "[prepare-stack] ${STACK_NAME}: docker not in PATH; skipped creating network '$net'."
    return 0
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "[prepare-stack] ${STACK_NAME}: Docker daemon not reachable; skipped creating network '$net'."
    return 0
  fi
  if docker network inspect "$net" >/dev/null 2>&1; then
    echo "[prepare-stack] ${STACK_NAME}: docker network '$net' already exists."
  else
    docker network create "$net"
    echo "[prepare-stack] ${STACK_NAME}: created docker network '$net'."
  fi
}

ensure_docker_network monitor

echo "[prepare-stack] ${STACK_NAME}: done. Next: edit stack.env if needed, then: docker compose up -d"
