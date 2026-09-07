#!/usr/bin/env bash
# Fail setup when the tools or mounted checkout are unavailable.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
test -w .
git rev-parse --show-toplevel >/dev/null
for tool in git bash python3 node shellcheck ruff actionlint hadolint zizmor docker; do
  command -v "${tool}" >/dev/null || { echo "Missing development tool: ${tool}" >&2; exit 1; }
done
node -e 'if (Number(process.versions.node.split(".")[0]) !== 26) process.exit(1)'
docker compose version
printf "%s\n" "Development tools ready. See .devcontainer/README.md for repository checks."
