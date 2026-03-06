# Scrutiny – disk health / SMART monitoring

[Scrutiny](https://github.com/AnalogJ/scrutiny) provides a web UI and alerting for disk SMART metrics. It helps you monitor drive health and catch failing disks early.

**Website / GitHub:** https://github.com/AnalogJ/scrutiny  
**Docker images:** https://github.com/AnalogJ/scrutiny/tree/master/docker  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Adjust `TZ` if needed.
2. **Verify devices**
   - Edit `docker-compose.yml` and ensure the `devices:` list and `/dev` mounts reflect the disks you want Scrutiny to monitor. The default example exposes `/dev`, which may be more than you need.
3. **Deploy**

   ```bash
   docker compose up -d
   ```

4. **Access**
   - Scrutiny listens on port `8080` inside the container.
   - Put it behind Caddy on the `monitor` network (e.g. `https://scrutiny.yourdomain.com` → `scrutiny:8080`).

## Configuration

| Item        | Details                                                      |
| ----------- | ------------------------------------------------------------ |
| **Access**  | Via Caddy (reverse-proxy to `scrutiny:8080`)                 |
| **Network** | `monitor` (so Caddy and monitoring/metrics stacks can reach it) |
| **Image**   | `ghcr.io/analogj/scrutiny:master-omnibus`                    |
| **Storage** | `scrutiny_config` (config), `scrutiny_influx` (metrics DB)   |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `scrutiny.yourdomain.com` → `scrutiny:8080` |

Scrutiny's configuration (alerts, notifications, thresholds) is stored in its config files under `/opt/scrutiny/config` inside the container. Those are persisted in the `scrutiny_config` volume.

## Notes

- This stack mounts `/run/udev` and `/dev` so Scrutiny can read SMART data from your disks. Review and restrict these mounts if needed for your environment.
- For email alerts and advanced options, see the upstream Scrutiny documentation.

