#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}"
cd "$ROOT_DIR"

echo "==> YAML parse checks"
python - <<'PY'
import yaml
from pathlib import Path

files = [
    Path("stacks/prometheus/prometheus.yml.example"),
    Path("stacks/prometheus/alerts.yml.example"),
    Path("stacks/alertmanager/alertmanager.yml.example"),
    Path("stacks/grafana-alloy/docker-compose.yml"),
    Path("documents/PROMETHEUS-SCRAPE-TARGETS.md"),
    Path("documents/TROUBLESHOOTING.md"),
]

for path in files:
    if path.suffix in {".yml", ".yaml"}:
        with path.open() as f:
            yaml.safe_load(f)
    print(f"OK {path}")
PY

echo "==> promtool rule checks"
docker run --rm \
  --entrypoint promtool \
  -v "$ROOT_DIR/stacks/prometheus/alerts.yml.example:/rules/alerts.yml:ro" \
  prom/prometheus:latest \
  check rules /rules/alerts.yml

if [[ -f "$CONFIG_DIR/prometheus/rules/alerts.yml" ]]; then
  docker run --rm \
    --entrypoint promtool \
    -v "$CONFIG_DIR/prometheus/rules/alerts.yml:/rules/alerts.yml:ro" \
    prom/prometheus:latest \
    check rules /rules/alerts.yml
fi

echo "==> amtool config checks"
docker run --rm \
  --entrypoint amtool \
  -v "$ROOT_DIR/stacks/alertmanager/alertmanager.yml.example:/etc/alertmanager/alertmanager.yml:ro" \
  -v "$ROOT_DIR/stacks/alertmanager/templates:/etc/alertmanager/templates:ro" \
  prom/alertmanager:latest \
  check-config /etc/alertmanager/alertmanager.yml

if [[ -f "$CONFIG_DIR/alertmanager/alertmanager.yml" ]]; then
  docker run --rm \
    --entrypoint amtool \
    -v "$CONFIG_DIR/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro" \
    -v "$CONFIG_DIR/alertmanager/templates:/etc/alertmanager/templates:ro" \
    prom/alertmanager:latest \
    check-config /etc/alertmanager/alertmanager.yml
fi

echo "==> Alloy config checks"
docker run --rm \
  -v "$ROOT_DIR/stacks/grafana-alloy/config.alloy.example:/etc/alloy/config.alloy:ro" \
  grafana/alloy:latest \
  fmt /etc/alloy/config.alloy >/dev/null

if [[ -f "$CONFIG_DIR/grafana-alloy/config.alloy" ]]; then
  docker run --rm \
    -v "$CONFIG_DIR/grafana-alloy/config.alloy:/etc/alloy/config.alloy:ro" \
    grafana/alloy:latest \
    fmt /etc/alloy/config.alloy >/dev/null
fi

echo "Monitoring config validation passed."
