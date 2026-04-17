#!/usr/bin/env bash
set -euo pipefail

if [[ "${SKIP_SECRETS_SCAN:-0}" == "1" ]]; then
  echo "[secrets] SKIP_SECRETS_SCAN=1 set; skipping staged secrets scan." >&2
  exit 0
fi

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "[secrets] gitleaks is required but was not found in PATH." >&2
  echo "[secrets] Install: https://github.com/gitleaks/gitleaks#installing" >&2
  exit 127
fi

if gitleaks protect --help >/dev/null 2>&1; then
  echo "[secrets] Scanning staged changes with gitleaks protect..."
  exec gitleaks protect --staged --redact --verbose
fi

echo "[secrets] gitleaks protect not available; scanning staged snapshot..."
tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "${tmp_dir}"
}
trap cleanup EXIT

staged_files="$(git diff --cached --name-only --diff-filter=ACMR)"
if [[ -z "${staged_files}" ]]; then
  echo "[secrets] No staged files to scan."
  exit 0
fi

while IFS= read -r file; do
  [[ -z "${file}" ]] && continue
  mkdir -p "${tmp_dir}/$(dirname "${file}")"
  git show ":${file}" > "${tmp_dir}/${file}"
done <<< "${staged_files}"

exec gitleaks detect --no-git --source "${tmp_dir}" --redact --verbose
