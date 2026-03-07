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
| **Access**  | Internal only; Prometheus scrapes `node-exporter:9100` on `monitor`    |
| **Network** | `monitor` — shared with Prometheus, Grafana, cAdvisor                 |
| **Host data** | Mounts host root (`/:/host:ro,rslave`) so metrics reflect the Docker host |

## Start

`docker compose up -d` from this directory.
