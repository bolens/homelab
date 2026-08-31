#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
STRICT=0
CHANGED_BASE=""
if [[ "${1:-}" == "--strict" ]]; then
  STRICT=1
  shift
fi
if [[ "${1:-}" == "--changed-base" && -n "${2:-}" ]]; then
  CHANGED_BASE="$2"
  shift 2
fi
if [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--strict] [--changed-base GIT_REVISION]" >&2
  exit 2
fi

run_optional_check() {
  local tool="$1"
  shift
  if command -v "$tool" >/dev/null 2>&1; then
    "$@"
  elif (( STRICT )); then
    echo "FAIL: $tool is unavailable." >&2
    return 1
  else
    echo "WARN: $tool is unavailable; check skipped." >&2
  fi
}

echo "Compiling Python helpers..."
python3 -m compileall -q scripts

echo "Parsing Compose YAML..."
python3 scripts/ci-parse-composes.py

echo "Rendering Compose configurations..."
compose_args=()
if [[ -n "$CHANGED_BASE" ]]; then
  compose_args+=(--changed-base "$CHANGED_BASE")
fi
python3 scripts/validate-compose-config.py "${compose_args[@]}"

echo "Auditing stack preparation scripts..."
python3 scripts/audit-prepare-scripts.py

echo "Auditing stack metadata..."
python3 scripts/audit-stack-metadata.py

echo "Auditing repository hygiene..."
python3 scripts/audit-repo-hygiene.py

echo "Validating dependency update configuration..."
python3 scripts/validate-dependency-config.py

echo "Checking generated documentation..."
python3 scripts/build-stack-catalog.py --check
python3 scripts/build-topology.py --check
python3 scripts/validate-topology-artifacts.py

echo "Checking YAML style..."
mapfile -t yaml_files < <(git ls-files '*.yaml' '*.yml' | while read -r file; do
  [[ -f "$file" ]] && printf '%s\n' "$file"
done)
run_optional_check yamllint yamllint -c .yamllint.yml "${yaml_files[@]}"

echo "Checking Markdown style..."
mapfile -t markdown_files < <(git ls-files '*.md' | while read -r file; do
  [[ -f "$file" ]] && printf '%s\n' "$file"
done)
run_optional_check markdownlint-cli2 markdownlint-cli2 --config .markdownlint.json \
  "${markdown_files[@]}"

echo "Checking repository shell helpers..."
mapfile -t shell_files < <(git ls-files '*.sh' | while read -r file; do
  [[ -f "$file" ]] && printf '%s\n' "$file"
done)
run_optional_check shellcheck shellcheck -S warning "${shell_files[@]}"

echo "Repository validation passed."
