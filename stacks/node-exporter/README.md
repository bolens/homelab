# Node Exporter

Prometheus Node Exporter for host-level metrics (CPU, memory, disk, network). Use with Prometheus and Grafana (e.g. dashboard **1860** – Node Exporter Full).

**Website:** https://prometheus.io/docs/guides/node-exporter/
**Docs:** https://prometheus.io/docs/guides/node-exporter/
**Docker image:** https://hub.docker.com/r/prom/node-exporter
**GitHub:** https://github.com/prometheus/node_exporter

## Quick start

1. Copy `stack.env.example` → `stack.env` (optional; used for TZ/locale if you add env_file).
2. Start the stack:

   ```bash
   docker compose up -d
   ```

3. Add a scrape job in your Prometheus config (`~/.config/prometheus/prometheus.yml`):

   ```yaml
   scrape_configs:
     - job_name: node
       static_configs:
         - targets: ["node-exporter:9100"]
   ```

4. Reload Prometheus, then in Grafana import dashboard **1860** (Node Exporter Full).

## Configuration

| Item        | Details                                                                 |
| ----------- | ----------------------------------------------------------------------- |
| **Access**  | Internal only; Prometheus scrapes `node-exporter:9100` on `telemetry`    |
| **Network** | `telemetry`, shared with Prometheus, Grafana, cAdvisor                 |
| **Host data** | Mounts host root (`/:/host:ro,rslave`) so metrics reflect the Docker host |

The container health check uses the lightweight `/` landing page. Prometheus
continues scraping `/metrics`; using `/metrics` for health would redundantly run
every enabled collector once per health interval.

## Start

`docker compose up -d` from this directory.

## Host-generated metrics

The opt-in `docker-compose.textfile.yml` enables the textfile collector at
`/host/var/lib/node_exporter/textfile_collector`, using the existing read-only
host-root mount. Set `NODE_EXPORTER_TEXTFILE_DIRECTORY` for another host path.
It adds no mount, privilege or published port. Combine it explicitly with the
base file and any existing override when deploying. Preparation does not
enable the collector or start metric-producing jobs.

Host jobs should write aggregate numeric metrics to a temporary file, set
read permissions and atomically rename it to a `.prom` file. Include the last
successful update timestamp so Prometheus can detect a stopped job rather than
silently retaining old values. Do not put credentials, personal identifiers,
program titles or stream URLs in metric labels. The optional Dispatcharr
maintenance helper supplies one such metrics file and alert rules.
