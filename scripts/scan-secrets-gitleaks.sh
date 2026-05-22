#!/usr/bin/env bash
# Run gitleaks against this homelab repo (git history + working tree).
#
# Usage (from anywhere):
#   ./scripts/scan-secrets-gitleaks.sh
#   ./scripts/scan-secrets-gitleaks.sh --no-git          # all files on disk (faster; includes gitignored e.g. stack.env)
#   ./scripts/scan-secrets-gitleaks.sh -c .gitleaks.toml # custom config
#
# Optional: place .gitleaks.toml or .gitleaksignore at the repo root to tune rules / paths.
# Install: https://github.com/gitleaks/gitleaks
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "scan-secrets-gitleaks.sh: gitleaks not found in PATH." >&2
  echo "Install: https://github.com/gitleaks/gitleaks#installing" >&2
  exit 127
fi

echo "scan-secrets-gitleaks.sh: scanning ${REPO}" >&2
exec gitleaks detect \
  --source "$REPO" \
  --redact \
  --verbose \
  "$@"
