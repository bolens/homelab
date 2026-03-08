# cAdvisor

Container resource metrics (CPU, memory, network, filesystem) for all containers on the host. Prometheus scrapes cAdvisor; Grafana displays the data (e.g. dashboard 893).

**Website:** https://github.com/google/cadvisor  
**Docs:** https://github.com/google/cadvisor/tree/master/docs  
**GitHub:** https://github.com/google/cadvisor  
**Docker image:** https://gcr.io/cadvisor/cadvisor  
**Releases:** https://github.com/google/cadvisor/releases  

## Quick start

1. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer).
2. Deploy **Prometheus** next (scrapes cAdvisor); then **Grafana** for dashboards.
3. Optional: open via Caddy (e.g. https://cadvisor.home) to see cAdvisor’s built-in UI.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `cadvisor:8080`) |
| **Network** | `monitor` — shared with Caddy, Prometheus, Grafana |
| **Privileged** | Required for full container and host visibility |

**Portainer:** Deploy as usual; no config files or volumes. The container runs privileged; ensure you’re comfortable with that on the host.

## Start

`docker compose up -d` from this directory.

## Troubleshooting

- **Container exited with code 137** — Exit 137 usually means the process was killed (SIGKILL), often by the OOM killer or a manual stop. The stack sets a 512M memory limit to reduce OOM risk. Restart with `docker compose up -d`. If it keeps exiting, increase the limit in `docker-compose.yml` (`deploy.resources.limits.memory`) or ensure the host has enough free RAM. You may see warnings in logs about some cgroup paths (e.g. net_cls, waydroid); cAdvisor continues and still reports Docker container stats.
- **cgroup v2 hosts** — On systems with cgroup v2 (e.g. Ubuntu 22.04+, kernel 5.15+), cAdvisor can log "invalid cross-device link" or similar for some paths; it often still reports container stats. If the container exits repeatedly, check logs and consider running a newer cAdvisor image when available with full cgroup v2 support.
