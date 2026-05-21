#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
# asking-ng: bootstraps from templates under examples/stack/ and examples/caddy/
# Optionally set ASKING_NG_PUBLIC_HOSTNAME before running (default: asking-ng.example.com)

STACK_ENV_TEMPLATE="$_PREPDIR/examples/stack/stack.env.template"
STACK_ENV_DEV_EXAMPLE="$_PREPDIR/examples/stack/stack.env.dev.example"
CADDY_TEMPLATE="$_PREPDIR/examples/caddy/caddy_snippet.conf.template"
PUBLIC_HOSTNAME="${ASKING_NG_PUBLIC_HOSTNAME:-asking-ng.example.com}"

prepare_stack_begin "$_PREPDIR"

if [[ -f "${STACK_ENV_TEMPLATE}" ]]; then
  if [[ ! -f stack.env ]]; then
    sed "s|{{PUBLIC_HOSTNAME}}|${PUBLIC_HOSTNAME}|g" "${STACK_ENV_TEMPLATE}" > stack.env
    prepare_stack_msg "created stack.env from stack.env.template — set secrets and review variables."
  else
    prepare_stack_msg "stack.env already exists (left unchanged)."
  fi
else
  prepare_stack_msg "no examples/stack/stack.env.template (skipped)."
fi

mkdir -p "$_PREPDIR/secrets"
prepare_stack_msg "ensured secrets/ directory exists for optional JWT PEM mounts."

if [[ -f "${STACK_ENV_DEV_EXAMPLE}" ]]; then
  if [[ ! -f stack.env.dev ]]; then
    cp "${STACK_ENV_DEV_EXAMPLE}" stack.env.dev
    prepare_stack_msg "created stack.env.dev from stack.env.dev.example (optional dev overrides)."
  else
    prepare_stack_msg "stack.env.dev already exists (left unchanged)."
  fi
else
  prepare_stack_msg "no examples/stack/stack.env.dev.example (skipped)."
fi

if [[ -f "$_PREPDIR/scripts/sync-example-artifacts.sh" ]]; then
  bash "$_PREPDIR/scripts/sync-example-artifacts.sh"
  prepare_stack_msg "caddy_snippet.conf rendered via scripts/sync-example-artifacts.sh."
elif [[ ! -f "$_PREPDIR/caddy_snippet.conf" ]] && [[ -f "${CADDY_TEMPLATE}" ]]; then
  sed "s|{{PUBLIC_HOSTNAME}}|${PUBLIC_HOSTNAME}|g" "${CADDY_TEMPLATE}" > "$_PREPDIR/caddy_snippet.conf"
  prepare_stack_msg "created caddy_snippet.conf from caddy_snippet.conf.template."
elif [[ -f "$_PREPDIR/caddy_snippet.conf" ]]; then
  prepare_stack_msg "caddy_snippet.conf already exists (left unchanged)."
else
  prepare_stack_msg "no caddy template or sync script (skipped)."
fi

prepare_stack_ensure_docker_network "monitor"
prepare_stack_end
