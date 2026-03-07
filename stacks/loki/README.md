# Loki – log aggregation

[Loki](https://grafana.com/oss/loki/) is a log aggregation system from Grafana, optimized for storing and querying logs with Prometheus-style labels. This stack runs a single-node Loki instance. Deploy **Promtail** (`stacks/promtail`) separately to ship host and container logs to Loki.

**Loki:** https://grafana.com/oss/loki/  
**Docker image:** https://hub.docker.com/r/grafana/loki  

## Quick start

1. **Config** (path must exist before deploy)

   From the `docker/` repo root:

   ```bash
   mkdir -p ~/.config/loki
   cp stacks/loki/loki-config.yml.example ~/.config/loki/loki-config.yml
   ```

   Edit if needed (storage paths, limits). When deploying from Portainer, set `LOKI_CONFIG_PATH` to the absolute path of this file.

2. Optionally copy `stack.env.example` → `stack.env` to set `TZ` or override the config path.

3. **Deploy**

   ```bash
   docker compose up -d
   ```

4. **Grafana** – Add Loki as a data source (e.g. `http://loki:3100`) or use provisioned datasources. Use **Explore** → **Loki** to query logs. Deploy `stacks/promtail` to ship logs into Loki.

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Loki HTTP API is internal on `monitor`; typically not exposed via Caddy   |
| **Config**  | Copy `loki-config.yml.example` → `~/.config/loki/loki-config.yml`; override with `LOKI_CONFIG_PATH` (e.g. in Portainer) |
| **Network** | `monitor` (so Grafana and Promtail can reach Loki)                         |
| **Storage** | `loki_data` volume (indexes, chunks, WAL)                                  |

## Notes

- This is a simple, single-node Loki suitable for homelab use. For HA or larger deployments, see the official Loki docs.
- By default, Loki stores data on local disk in the `loki_data` volume. The example config sets **retention** to **30 days** (`retention_period: 720h`) with the compactor enforcing deletion; adjust in `loki-config.yml` if needed. Ensure the host has enough disk space for your log retention needs.

