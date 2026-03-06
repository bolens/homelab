# Loki + Promtail – log aggregation

[Loki](https://grafana.com/oss/loki/) is a log aggregation system from Grafana, optimized for storing and querying logs with Prometheus-style labels. [Promtail](https://grafana.com/docs/loki/latest/clients/promtail/) is the agent that ships logs to Loki.

This stack runs a single-node Loki instance and a Promtail agent that tails system and Docker logs on the host.

**Loki:** https://grafana.com/oss/loki/  
**Promtail:** https://grafana.com/docs/loki/latest/clients/promtail/  
**Docker images:** `grafana/loki`, `grafana/promtail`  

## Quick start

1. **Config files**

   From this directory:

   ```bash
   cp loki-config.yml.example loki-config.yml
   cp promtail-config.yml.example promtail-config.yml
   ```

   Adjust them as needed (storage paths, scrape configs, limits).

2. **Environment**
   - Optionally copy `stack.env.example` → `stack.env` to set `TZ`.

3. **Deploy**

   ```bash
   docker compose up -d
   ```

4. **Hook up Grafana**
   - In Grafana (existing stack), add a Loki data source pointing to `http://loki:3100`.

## Configuration

| Item        | Details                                                                    |
| ----------- | -------------------------------------------------------------------------- |
| **Access**  | Loki HTTP API is internal on `monitor`; typically not exposed via Caddy   |
| **Network** | `monitor` (so Grafana and other infra stacks can reach Loki)              |
| **Images**  | `grafana/loki:2.9.8`, `grafana/promtail:2.9.8`                            |
| **Storage** | `loki_data` volume (indexes, chunks, WAL)                                  |

Promtail tails:

- `/var/log/*log` for system logs.
- `/var/lib/docker/containers/*/*-json.log` for Docker container logs.

You can customize `promtail-config.yml` to add or remove log sources and labels.

## Notes

- This is a simple, single-node Loki suitable for homelab use. For HA or larger deployments, see the official Loki docs.
- By default, Loki stores data on local disk in the `loki_data` volume. Ensure the host has enough disk space for your log retention needs.

