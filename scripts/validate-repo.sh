#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

echo "Compiling Python helpers..."
python3 -m compileall -q scripts

echo "Parsing Compose YAML..."
python3 scripts/ci-parse-composes.py

if command -v shellcheck >/dev/null 2>&1; then
  echo "Checking repository shell helpers..."
  mapfile -t shell_files < <(find scripts -maxdepth 1 -type f -name '*.sh' -print | sort)
  shellcheck -S warning "${shell_files[@]}"
else
  echo "WARN: shellcheck is unavailable; shell lint skipped." >&2
fi

echo "Repository validation passed."
