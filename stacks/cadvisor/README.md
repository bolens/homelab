# cAdvisor

Container resource metrics (CPU, memory, network, filesystem) for all containers on the host. Prometheus scrapes cAdvisor; Grafana displays the data (e.g. dashboard 893).

## Quick start

1. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer).
2. Deploy **Prometheus** next (scrapes cAdvisor); then **Grafana** for dashboards.
3. Optional: open via Caddy (e.g. https://cadvisor.home) to see cAdvisor’s built-in UI.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `cadvisor:8080`) |
| **Network** | `monitor` — shared with Caddy, Prometheus, Grafana |
| **Privileged** | Required for full container and host visibility |

**Portainer:** Deploy as usual; no config files or volumes. The container runs privileged; ensure you’re comfortable with that on the host.

## Start

`docker compose up -d` from this directory.
