# Grafana

Dashboard and visualization for Prometheus (and other datasources). Use with the Prometheus and cAdvisor stacks for host and container metrics.

**Website:** https://grafana.com  
**Docs:** https://grafana.com/docs/grafana/latest/  
**GitHub:** https://github.com/grafana/grafana  
**Docker image:** https://hub.docker.com/r/grafana/grafana  
**Releases:** https://github.com/grafana/grafana/releases  

## Quick start

1. Deploy **Prometheus** and **cAdvisor** first so Prometheus is scraping; then deploy this stack. See the main [docker README](../../README.md) section **Step-by-step: Grafana & Prometheus integration** for the full order.
2. Copy `stack.env.example` → `stack.env` (optional: set `GF_SERVER_ROOT_URL`; can leave file empty).
3. Copy `datasources.yml.example` → `~/.config/grafana/datasources.yml` (or another host path) and edit it if needed; this file defines the Prometheus datasource.
4. **Dashboard provisioning (required for compose):** Create the dashboards dir and copy the provisioning config so the stack can mount it. From the `docker/` repo root:
   ```bash
   mkdir -p ~/.config/grafana/provisioning_dashboards/json
   cp stacks/grafana/provisioning_dashboards.example/default.yaml ~/.config/grafana/provisioning_dashboards/
   ```
   You can add dashboard JSON files to `~/.config/grafana/provisioning_dashboards/json/` later (see **Dashboards** below). From Portainer, set `GRAFANA_DASHBOARDS_PATH` to the absolute path of this dir (e.g. `/home/youruser/.config/grafana/provisioning_dashboards`).
5. Start: `docker compose up -d` from this directory (CLI deploy) so the default paths resolve, or set `GRAFANA_DATASOURCES_PATH` and `GRAFANA_DASHBOARDS_PATH` explicitly (see Portainer notes below).
6. Open via Caddy (e.g. https://grafana.yourdomain.com). If you did not set `GF_SECURITY_DISABLE_INITIAL_ADMIN_CREATION=true`, default login is `admin` / `admin` (change on first use). If you disabled initial admin, see **First-time login** below.
7. Prometheus is pre-configured as the default datasource via `datasources.yml`. If you deploy **Loki** (`stacks/loki`), the same file provisions Loki; use **Explore** → **Loki** to query logs. Deploy **Promtail** (`stacks/promtail`) to ship host and container logs to Loki.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `grafana:3000`) |
| **Volume** | `grafana_data` (dashboards, users, settings) |
| **Network** | `monitor` — shared with Caddy, Prometheus, cAdvisor |
| **Env** | See [ENV-VARS.md](../../documents/ENV-VARS.md) and [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) for TZ/locale and shared resources. Optional: `GF_SERVER_ROOT_URL`, `GF_SECURITY_*`, `GRAFANA_DATASOURCES_PATH` |

**Portainer:** Use “Git repository” or paste the compose; when deploying from Portainer you **must** set `GRAFANA_DATASOURCES_PATH` in the stack’s Environment to the **absolute path** of your `datasources.yml` on the host (e.g. `/home/youruser/.config/grafana/datasources.yml` or `/opt/grafana/datasources.yml`), otherwise the default becomes `/.config/grafana/datasources.yml` and the stack will fail. Put the file on the host first (copy from `datasources.yml.example`).

**Root URL:** If you access Grafana at a different URL (e.g. https://grafana.yourdomain.com), set `GF_SERVER_ROOT_URL` in `stack.env` to that URL so login redirects work. For TZ/locale and shared resources, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

**Default login:** Unless you set `GF_SECURITY_DISABLE_INITIAL_ADMIN_CREATION=true`, Grafana creates an initial admin user. Default credentials are **admin** / **admin**; change the password on first login.

**First-time login (no admin yet):** If you set `GF_SECURITY_DISABLE_INITIAL_ADMIN_CREATION=true`, Grafana does not create a default admin. Either (1) set `GF_USERS_ALLOW_SIGN_UP=true` in `stack.env`, restart Grafana (`docker compose up -d -f ...`), open the login page and use “Sign up” to create your account, then set `GF_USERS_ALLOW_SIGN_UP=false` again and restart; or (2) set `GF_SECURITY_DISABLE_INITIAL_ADMIN_CREATION=false`, remove the `grafana_data` volume and bring the stack up again so Grafana creates the default `admin` / `admin` (you will lose existing dashboards/data).

## Logs (Loki)

If you deploy **stacks/loki**, the provisioned `datasources.yml` already includes Loki at `http://loki:3100`. In Grafana go to **Explore** → choose **Loki** to run LogQL queries. Deploy **stacks/promtail** (and optionally **stacks/vector**) to ship logs to Loki; all must use the `monitor` network.

## Dashboards

**Option A – Import by ID (needs egress):** Open **Import** (e.g. `https://grafana.yourdomain.com/dashboard/import`) and enter a dashboard ID. The Grafana container must reach grafana.com; the stack sets DNS (1.1.1.1, 8.8.8.8). If you get "Dashboard import failed", use Option B.

**Option B – Provision from JSON (no egress):** When "Import by ID" fails, add dashboards by dropping JSON files into your provisioning folder. On your machine (browser can reach grafana.com), open a dashboard page (e.g. https://grafana.com/grafana/dashboards/1860), click **Download JSON**, save as e.g. `node-exporter.json` into `~/.config/grafana/provisioning_dashboards/json/`. Restart Grafana (`docker compose up -d`); the dashboard appears under **Dashboards**. Suggested downloads:

| ID    | Dashboard            |
|-------|----------------------|
| 1860  | Node Exporter Full   |
| 893   | cAdvisor (containers)|
| 3662  | Prometheus 2.0       |
| 7587  | Blackbox Exporter    |

## Start

`docker compose up -d` from this directory.
