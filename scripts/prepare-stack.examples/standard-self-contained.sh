#!/usr/bin/env bash
# Example: self-contained verbose prepare (no shared lib). Copy into a stack only if you
# intentionally avoid sourcing ../../scripts/prepare-stack-lib.sh.
#
# Typical stack: stacks/<name>/prepare-stack.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
STACK_NAME="$(basename "$SCRIPT_DIR")"

echo "[prepare-stack] ${STACK_NAME}: starting..."

if [[ -f stack.env.example ]]; then
  if [[ ! -f stack.env ]]; then
    cp stack.env.example stack.env
    echo "[prepare-stack] ${STACK_NAME}: created stack.env — set secrets and review variables before docker compose up."
  else
    echo "[prepare-stack] ${STACK_NAME}: stack.env already exists (left unchanged)."
  fi
else
  echo "[prepare-stack] ${STACK_NAME}: no stack.env.example found (skipped)."
fi

if [[ -f caddy_snippet.conf.example ]]; then
  if [[ ! -f caddy_snippet.conf ]]; then
    cp caddy_snippet.conf.example caddy_snippet.conf
    echo "[prepare-stack] ${STACK_NAME}: created caddy_snippet.conf — replace placeholder hostname; reload Caddy after changes."
  else
    echo "[prepare-stack] ${STACK_NAME}: caddy_snippet.conf already exists (left unchanged)."
  fi
else
  echo "[prepare-stack] ${STACK_NAME}: no caddy_snippet.conf.example (skipped)."
fi

echo "[prepare-stack] ${STACK_NAME}: done. Next: docker compose up -d"
