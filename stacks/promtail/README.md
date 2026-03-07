# Promtail

[Promtail](https://grafana.com/docs/loki/latest/clients/promtail/) is the log-shipping agent for Loki. It tails log files on the host and pushes them to a Loki instance. Deploy this stack **after** the Loki stack so logs are available in Grafana (Explore → Loki).

**Docs:** https://grafana.com/docs/loki/latest/clients/promtail/  
**Docker image:** https://hub.docker.com/r/grafana/promtail  

## Dependencies

- **Loki** must be running and reachable at `http://loki:3100` on the `monitor` network (e.g. deploy `stacks/loki` first).

## Quick start

1. **Config** (path must exist before deploy)

   From the `docker/` repo root:

   ```bash
   mkdir -p ~/.config/promtail
   cp stacks/promtail/promtail-config.yml.example ~/.config/promtail/promtail-config.yml
   ```

   Edit if needed (e.g. add log paths or labels). When deploying from Portainer, set `PROMTAIL_CONFIG_PATH` to the absolute path of this file.

2. Optionally copy `stack.env.example` → `stack.env` to set `TZ` or override the config path.

3. **Deploy**

   ```bash
   docker compose up -d
   ```

4. In Grafana, use **Explore** → **Loki** to query logs (e.g. `{job="docker"}` or `{job="varlogs"}`).

## Configuration

| Item        | Details                                                                 |
| ----------- | ----------------------------------------------------------------------- |
| **Access**  | Internal only; pushes to `loki:3100` on `monitor`                       |
| **Config**  | Copy `promtail-config.yml.example` → `~/.config/promtail/promtail-config.yml`; override with `PROMTAIL_CONFIG_PATH` (e.g. in Portainer) |
| **Network** | `monitor` — same as Loki and Grafana                                   |

Default scrape config:

- **System:** `/var/log/*log` (job `varlogs`)
- **Docker:** `/var/lib/docker/containers/*/*-json.log` (job `docker`)

Customize `~/.config/promtail/promtail-config.yml` to add or remove sources and labels.
