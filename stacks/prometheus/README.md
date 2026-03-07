# Prometheus

Metrics collection and storage. Scrapes cAdvisor (container metrics) and itself. Grafana uses Prometheus as a datasource for dashboards.

**Website:** https://prometheus.io  
**Docs:** https://prometheus.io/docs/introduction/overview/  
**GitHub:** https://github.com/prometheus/prometheus  
**Docker image:** https://hub.docker.com/r/prom/prometheus  
**Releases:** https://github.com/prometheus/prometheus/releases  

## Quick start

1. **Config file:** Copy `prometheus.yml.example` to `~/.config/prometheus/prometheus.yml` (create the directory if needed). The example includes scrape jobs (self, cAdvisor, node-exporter), an `alerting` block to `alertmanager:9093`, and `rule_files` pointing at `alerts.yml`. The stack mounts the file read-only.
2. **Alert rules:** Create `~/.config/prometheus/rules` and copy `alerts.yml.example` to `~/.config/prometheus/rules/alerts.yml`. The example rules include InstanceDown, NodeMemoryHigh, NodeDiskSpaceLow, ProbeDown (Blackbox), and PrometheusConfigReloadFailure. If you use a different path, set `PROMETHEUS_RULES_PATH` in `stack.env` to that directory.
3. Deploy **cAdvisor** first (so Prometheus has a target to scrape). For the full order (network → Caddy → Prometheus → cAdvisor → Grafana), see the main [docker README](../../README.md) section **Step-by-step: Grafana & Prometheus integration**.
4. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer).
5. Open via Caddy (e.g. https://prometheus.yourdomain.com) to run PromQL queries, check targets (Status → Targets), or view firing alerts (Alerts).

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `prometheus:9090`) |
| **Config** | `~/.config/prometheus/prometheus.yml` (copy from `prometheus.yml.example`; edit on the host) |
| **Volume** | `prometheus_data` (time-series data); retention default **30d** (set `PROMETHEUS_RETENTION_TIME` in `stack.env` to override, e.g. `15d`, `90d`) |
| **Network** | `monitor` — shared with Caddy, Grafana, cAdvisor |

**Config path override:** Set `PROMETHEUS_CONFIG_PATH` (e.g. in `stack.env` or Portainer env) to an absolute path if you use a different location (e.g. `/opt/prometheus/prometheus.yml`).

**Rules path override:** Set `PROMETHEUS_RULES_PATH` to the absolute path of the directory containing `alerts.yml` (e.g. `/home/youruser/.config/prometheus/rules` or `/opt/prometheus/rules`). Required when deploying from Portainer so the rules directory is mounted correctly.

### Using this stack in Portainer

**You must set `PROMETHEUS_CONFIG_PATH` when deploying from Portainer.** Portainer does not set `$HOME`, so the default path becomes `/.config/prometheus/prometheus.yml`, which does not exist on the host; the stack will then fail with a mount error (“mount a directory onto a file”). Set the variable to the **absolute path** of your config file on the host.

1. **Put the config file on the host** where Docker (and Portainer) run, e.g.:
   - `~/.config/prometheus/prometheus.yml` → absolute path: `/home/youruser/.config/prometheus/prometheus.yml` (replace `youruser` with your username)
   - or `/opt/prometheus/prometheus.yml` (create the directory, copy `prometheus.yml.example` to `prometheus.yml` there).
2. **Create the stack** in Portainer (Stacks → Add stack → paste the compose, or deploy from Git).
3. **Add an environment variable** (required for Portainer):
   - Name: `PROMETHEUS_CONFIG_PATH`
   - Value: the **exact absolute path** to the `prometheus.yml` file on the host (e.g. `/home/youruser/.config/prometheus/prometheus.yml` or `/opt/prometheus/prometheus.yml`).
4. Deploy the stack. Prometheus will read the config from that path.

**Adding targets:** Edit your config file and add a `scrape_configs` entry. Reload without restart: `curl -X POST http://prometheus:9090/-/reload` (or from host via Caddy, or restart the stack).

## Start

`docker compose up -d` from this directory.
