#!/usr/bin/env bash
set -euo pipefail

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "pre-commit-gitleaks.sh: gitleaks is required." >&2
  echo "Install it from https://github.com/gitleaks/gitleaks#installing" >&2
  exit 1
fi

exec gitleaks git --staged --redact --no-banner .
