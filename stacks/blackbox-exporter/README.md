# Blackbox Exporter

Prometheus Blackbox Exporter for probing endpoints over HTTP, TCP, and other protocols. Use it with Prometheus and Alertmanager to create synthetic checks (e.g. "can I reach my tunnel hostname from inside the homelab?").

**Website:** https://prometheus.io/docs/blackbox_exporter/latest/
**Docs:** https://prometheus.io/docs/blackbox_exporter/configuration/
**Docker image:** https://hub.docker.com/r/prom/blackbox-exporter
**GitHub:** https://github.com/prometheus/blackbox_exporter

## Quick start

1. From this directory, copy `stack.env.example` → `stack.env` and adjust if needed.
2. Copy `blackbox.yml.example` to `~/.config/blackbox-exporter/blackbox.yml` (create the directory if needed). Edit that file to customize probe modules; defaults include `http_2xx` and `tcp_connect`. When deploying from Portainer, set `BLACKBOX_CONFIG_PATH` to the absolute path of that file.
3. Start the stack:

   ```bash
   docker compose up -d
   ```

4. Point Prometheus at the exporter (e.g. target `blackbox-exporter:9115` on the `telemetry` network) and use `module=` query params for probes.

## Configuration

| Item        | Details                                                                 |
| ----------- | ----------------------------------------------------------------------- |
| **Access**  | Internal only; Prometheus scrapes `blackbox-exporter:9115` on `telemetry` |
| **Config**  | Copy `blackbox.yml.example` to `~/.config/blackbox-exporter/blackbox.yml`; override with `BLACKBOX_CONFIG_PATH` (e.g. in Portainer) |
| **Network** | Internal `telemetry` for scrapes and a stack-owned `probe-egress` bridge for outbound DNS and probes. No host ports are published. |
| **Env**     | See `stack.env.example` and `documents/ENV-VARS.md` for TZ/locale.     |

The exporter needs outbound access to probe public endpoints. Attaching it only
to an internal network causes DNS failures even while its health check and
Prometheus scrape succeed. Compose creates `probe-egress`; preparation creates
only the shared internal `telemetry` network. Existing deployments must apply
the updated Compose networking. Keep `telemetry` internal.

Check `probe_success`, rather than only `up`, to verify monitored endpoints.
`up` confirms Prometheus can scrape the exporter even when its probe fails.
The Caddy snippet is optional and requires explicitly attaching the exporter to
Caddy's ingress network. The default deployment exposes no browser route.

### Example Prometheus scrape config

Add a job to your `prometheus.yml` similar to:

```yaml
scrape_configs:
  - job_name: 'blackbox'
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
          - https://caddy.home
          - https://example.yourdomain.com
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115
```
