# Onionprobe

Tor Onion Services monitoring: continuously probes a set of onion endpoints, exports metrics to Prometheus, and provides Grafana dashboards and Alertmanager alerts. Uses the [official Tor Project Onionprobe](https://onionservices.torproject.org/apps/web/onionprobe/) stack with service names prefixed so it does not clash with your existing Prometheus/Grafana.

**Website:** https://onionservices.torproject.org/apps/web/onionprobe/  
**Docs:** https://onionservices.torproject.org/apps/web/onionprobe/  
**GitHub:** https://gitlab.torproject.org/tpo/onion-services/onionprobe  
**Releases:** https://gitlab.torproject.org/tpo/onion-services/onionprobe/-/releases  

## Quick start

1. **Clone the upstream repo** (required once):

   ```bash
   ./clone-repo.sh
   ```

   This creates `./repo` with the official Onionprobe source and configs.

2. **Optional:** copy `stack.env.example` to `stack.env` and set `GRAFANA_DATABASE_PASSWORD` (use a strong random password, e.g. `openssl rand -hex 32`) and `GF_SERVER_ROOT_URL` (e.g. `https://onionprobe.home`).

3. **Deploy:**

   ```bash
   docker compose up -d
   ```

   First run will build the Onionprobe and Tor images from the repo (a few minutes). The configurator generates the endpoint list; the main probe may take a short while to produce metrics.

4. **Access:** Open Grafana via Caddy at https://onionprobe.home (or the hostname you added to Caddy). Default login is `admin` / `admin` unless you change it.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host ports; reverse proxy to `op-grafana:3000`) |
| **Network** | `onionprobe` (internal); `monitor` (op-grafana, op-prometheus, op-alertmanager, op-onionprobe for Caddy) |
| **Services** | op-grafana (3000), op-prometheus (9090), op-alertmanager (9093), op-onionprobe (exporter 9935); op-tor, op-configurator, op-postgres |
| **Build** | Images built from `./repo` (Onionprobe + Tor); clone repo before first up |

Optional Caddy hostnames for other UIs (same stack):

- **Onionprobe exporter** (metrics): `onionprobe-exporter.home` → `op-onionprobe:9935`
- **Prometheus:** `onionprobe-prometheus.home` → `op-prometheus:9090`
- **Alertmanager:** `onionprobe-alertmanager.home` → `op-alertmanager:9093`

## Caddy reverse proxy

Example (main UI – Grafana):

```
onionprobe.home, onionprobe.local {
  tls internal
  reverse_proxy op-grafana:3000
}
```

Ensure the stack is on the `monitor` network so Caddy can reach `op-grafana`.

## Start

From this directory: `./clone-repo.sh` once, then `docker compose up -d`.  
In Portainer: clone the repo into the stack folder (or mount it), add the stack, ensure `monitor` network exists, deploy.
