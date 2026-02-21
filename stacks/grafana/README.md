# Grafana

Dashboard and visualization for Prometheus (and other datasources). Use with the Prometheus and cAdvisor stacks for host and container metrics.

## Quick start

1. Deploy **Prometheus** and **cAdvisor** first so Prometheus is scraping; then deploy this stack.
2. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer).
3. Open via Caddy (e.g. https://grafana.home). Default login: `admin` / `admin` (change on first use).
4. Prometheus is pre-configured as the default datasource (see `provisioning/datasources/`).

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `grafana:3000`) |
| **Volume** | `grafana_data` (dashboards, users, settings) |
| **Network** | `monitor` — shared with Caddy, Prometheus, cAdvisor |
| **Env** | See [ENV-VARS.md](../../documents/ENV-VARS.md). Optional: `GF_SERVER_ROOT_URL`, `GF_SECURITY_*` |

**Portainer:** Use “Git repository” or paste the compose; ensure the `provisioning` folder is present (bind-mounted). If you deploy from Git, the repo path must include `stacks/grafana` so `./provisioning` resolves.

**Root URL:** If you access Grafana at a different URL (e.g. https://grafana.yourdomain.com), set `GF_SERVER_ROOT_URL` in the stack env or `.env` to that URL so login redirects work.

## Suggested dashboards

After adding the stack, in Grafana: **Dashboards** → **Import** and use these IDs (from grafana.com):

- **893** – cAdvisor (containers)
- **1860** – Node Exporter (host metrics; add node_exporter later if needed)
- **3662** – Prometheus 2.0 overview

## Start

`docker compose up -d` from this directory.
