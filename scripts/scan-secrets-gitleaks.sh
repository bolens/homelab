#!/usr/bin/env bash
# Run gitleaks against this homelab repo (git history + working tree).
#
# Usage (from anywhere):
#   ./scripts/scan-secrets-gitleaks.sh
#   ./scripts/scan-secrets-gitleaks.sh git               # full history (default)
#   ./scripts/scan-secrets-gitleaks.sh dir               # files on disk, including ignored files
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
mode="${1:-git}"
if (($#)); then shift; fi

case "$mode" in
  --help|-h)
    echo "Usage: $0 [git|dir] [gitleaks options]"
    echo "  git  Scan complete Git history (default)"
    echo "  dir  Scan files on disk, including ignored runtime files"
    exit 0
    ;;
  git)
    cd "$REPO"
    exec gitleaks git --redact --verbose "$@" .
    ;;
  dir)
    exec gitleaks dir --redact --verbose "$@" "$REPO"
    ;;
  *)
    echo "Usage: $0 [git|dir] [gitleaks options]" >&2
    exit 2
    ;;
esac
