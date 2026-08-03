#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: find_apache2_containers.sh [--help|--health|--version]

List host apache2 processes and identify their Docker container, if any.
Run this on the Docker host. Reading another user's /proc entries may require
elevated privileges.
EOF
}

case "${1:-}" in
  --help) usage; exit 0 ;;
  --health) echo "OK"; exit 0 ;;
  --version) echo "find_apache2_containers.sh 2.0"; exit 0 ;;
  "") ;;
  *) usage >&2; exit 2 ;;
esac

command -v pgrep >/dev/null 2>&1 || {
  echo "find_apache2_containers.sh: pgrep is required." >&2
  exit 127
}

mapfile -t pids < <(pgrep -x apache2 || true)
if ((${#pids[@]} == 0)); then
  echo "No apache2 processes found."
  exit 0
fi

docker_available=false
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  docker_available=true
fi

for pid in "${pids[@]}"; do
  cgroup="$(grep -Eo '[0-9a-f]{64}' "/proc/${pid}/cgroup" 2>/dev/null | head -n 1 || true)"
  if [[ -z "$cgroup" ]]; then
    echo "PID $pid is not in a Docker container (or its cgroup is unreadable)."
    continue
  fi

  if [[ "$docker_available" == true ]]; then
    container_name="$(docker inspect --format '{{.Name}}' "$cgroup" 2>/dev/null | sed 's#^/##' || true)"
  else
    container_name=""
  fi

  if [[ -n "$container_name" ]]; then
    echo "PID $pid is in Docker container: $container_name ($cgroup)"
  else
    echo "PID $pid is in Docker container: $cgroup (name unavailable)"
  fi
done
