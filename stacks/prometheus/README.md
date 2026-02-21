# Prometheus

Metrics collection and storage. Scrapes cAdvisor (container metrics) and itself. Grafana uses Prometheus as a datasource for dashboards.

## Quick start

1. Deploy **cAdvisor** first (so Prometheus has a target to scrape).
2. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer).
3. Open via Caddy (e.g. https://prometheus.home) to run PromQL queries or check targets (Status → Targets).

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `prometheus:9090`) |
| **Config** | `prometheus.yml` in this folder (scrape config; safe to commit) |
| **Volume** | `prometheus_data` (time-series data; retention uses disk) |
| **Network** | `monitor` — shared with Caddy, Grafana, cAdvisor |

**Portainer:** Deploy from Git so `prometheus.yml` is present, or copy `prometheus.yml` to the host and set the volume to that path (e.g. `/opt/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro`).

**Adding targets:** Edit `prometheus.yml` and add a `scrape_configs` entry. Reload without restart: `curl -X POST http://prometheus:9090/-/reload` (or from host: use Caddy URL with a reload script, or restart the stack).

## Start

`docker compose up -d` from this directory.
