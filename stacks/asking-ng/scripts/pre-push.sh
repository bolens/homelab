#!/usr/bin/env bash
set -euo pipefail

if [[ "${SKIP_PRE_PUSH:-0}" == "1" ]]; then
  echo "[pre-push] SKIP_PRE_PUSH=1 set; skipping pre-push checks."
  exit 0
fi

echo "[pre-push] Inspecting pushed changes..."

if git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}" >/dev/null 2>&1; then
  changed_files="$(git diff --name-only --diff-filter=ACMR "@{upstream}...HEAD")"
else
  echo "[pre-push] No upstream branch found; running full checks."
  changed_files=""
fi

if [[ -n "${changed_files}" ]]; then
  non_docs_count="$(
    printf '%s\n' "${changed_files}" | rg -v '^(docs/|.*\.md$)' | wc -l | tr -d '[:space:]'
  )"
  if [[ "${non_docs_count}" == "0" ]]; then
    echo "[pre-push] Docs-only changes detected; skipping typecheck/test."
    exit 0
  fi
fi

echo "[pre-push] Running typecheck..."
pnpm run typecheck

echo "[pre-push] Running test suite..."
pnpm run test

echo "[pre-push] Checks passed."
