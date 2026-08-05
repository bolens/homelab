#!/usr/bin/env bash
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
errors=0
warnings=0

ok() { printf 'OK    %s\n' "$*"; }
warn() { printf 'WARN  %s\n' "$*"; warnings=$((warnings + 1)); }
fail() { printf 'FAIL  %s\n' "$*"; errors=$((errors + 1)); }

expected_networks=()
mount_paths=()

while (($#)); do
  case "$1" in
    --network)
      [[ $# -ge 2 ]] || { echo "--network requires a name" >&2; exit 2; }
      expected_networks+=("$2")
      shift 2
      ;;
    --mount)
      [[ $# -ge 2 ]] || { echo "--mount requires a path" >&2; exit 2; }
      mount_paths+=("$2")
      shift 2
      ;;
    --help|-h)
      echo "Usage: $0 [--network NAME]... [--mount PATH]..."
      echo "Read-only checks for prerequisites, repository safety, Compose files, Docker, networks, and mounts."
      echo "Environment: HOMELAB_EXPECTED_NETWORKS (space-separated), HOMELAB_MOUNT_PATHS (colon-separated)."
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -n "${HOMELAB_EXPECTED_NETWORKS:-}" ]]; then
  read -r -a env_networks <<< "$HOMELAB_EXPECTED_NETWORKS"
  expected_networks+=("${env_networks[@]}")
fi
if [[ -n "${HOMELAB_MOUNT_PATHS:-}" ]]; then
  IFS=: read -r -a env_mounts <<< "$HOMELAB_MOUNT_PATHS"
  mount_paths+=("${env_mounts[@]}")
fi

echo "Homelab repository doctor"
echo

for command in git python3 docker; do
  if command -v "$command" >/dev/null 2>&1; then
    ok "$command is installed"
  else
    fail "$command is not installed"
  fi
done

if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    ok "Docker Compose plugin is installed"
  else
    fail "Docker Compose plugin is unavailable"
  fi
  if docker info >/dev/null 2>&1; then
    ok "Docker daemon is reachable"
    for network in "${expected_networks[@]}"; do
      if docker network inspect "$network" >/dev/null 2>&1; then
        ok "Docker network '$network' exists"
      else
        warn "Docker network '$network' is absent (create it only if a selected stack uses it)"
      fi
    done
  else
    warn "Docker daemon is not reachable; live checks skipped"
  fi
fi

for optional in gitleaks shellcheck; do
  if command -v "$optional" >/dev/null 2>&1; then
    ok "optional tool '$optional' is installed"
  else
    warn "optional tool '$optional' is not installed"
  fi
done

if git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ok "repository metadata is valid"
else
  fail "$REPO is not a Git worktree"
fi

tracked_sensitive="$(git -C "$REPO" ls-files | grep -E '(^|/)(stack\.env|\.env|caddy_snippet\.conf)$' || true)"
if [[ -n "$tracked_sensitive" ]]; then
  fail "runtime env/Caddy files are tracked; inspect with: git ls-files | grep -E '(^|/)(stack\\.env|\\.env|caddy_snippet\\.conf)$'"
else
  ok "runtime env and Caddy files are not tracked"
fi

if python3 "$REPO/scripts/ci-parse-composes.py"; then
  ok "Compose YAML files parse successfully"
else
  fail "one or more Compose YAML files failed to parse"
fi

stack_count="$(find "$REPO/stacks" -mindepth 1 -maxdepth 1 -type d | wc -l)"
compose_count="$(find "$REPO/stacks" -mindepth 2 -maxdepth 2 -name docker-compose.yml | wc -l)"
example_count="$(find "$REPO/stacks" -mindepth 2 -maxdepth 2 -name stack.env.example | wc -l)"
printf 'INFO  stacks=%s compose_files=%s env_examples=%s\n' "$stack_count" "$compose_count" "$example_count"

for mount_path in "${mount_paths[@]}"; do
  if [[ -e "$mount_path" ]]; then
    if mountpoint -q "$mount_path"; then
      ok "$mount_path is a mount point"
    elif findmnt -T "$mount_path" -n >/dev/null 2>&1; then
      ok "$mount_path is on a mounted filesystem"
    else
      warn "$mount_path exists but is not on a distinct mounted filesystem"
    fi
  fi
done

echo
printf 'Result: %s failure(s), %s warning(s)\n' "$errors" "$warnings"
((errors == 0))
