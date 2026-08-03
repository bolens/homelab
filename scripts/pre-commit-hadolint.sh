#!/usr/bin/env bash
set -euo pipefail

if (($# == 0)); then
  exit 0
fi

if ! command -v hadolint >/dev/null 2>&1; then
  echo "pre-commit-hadolint.sh: hadolint is required." >&2
  echo "Install it from https://github.com/hadolint/hadolint#install" >&2
  exit 1
fi

exec hadolint --config .hadolint.yaml "$@"
