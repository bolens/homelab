# Watchtower

Automatically updates running containers when new images are available. Uses the Docker socket on the host.

This stack uses **nickfedor/watchtower** (maintained fork). The original containrrr/watchtower image is archived and fails on Docker 29+ with "client version 1.25 is too old. Minimum supported API version is 1.44".

**Website:** https://containrrr.dev/watchtower  
**Docs:** https://containrrr.dev/watchtower/  
**GitHub:** https://github.com/nickfedor/watchtower  
**Docker image:** https://hub.docker.com/r/nickfedor/watchtower  
**Releases:** https://github.com/nickfedor/watchtower/releases  

## Quick start

`docker compose up -d` from this directory (or deploy as a stack in Portainer). By default: polls every 24 hours and removes old images after updating.

## Configuration

| Item | Details |
|------|---------|
| **Volume** | `/var/run/docker.sock` (required) |
| **Network** | `monitor` (external) — so Prometheus can scrape `watchtower:80` |
| **Env** | See [ENV-VARS.md](../../documents/ENV-VARS.md) and [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) for TZ/locale and shared resources. |

**Key env vars (in `docker-compose.yml`):**

- `WATCHTOWER_POLL_INTERVAL=86400` — check every 24h. Override or use `--schedule "0 0 3 * * *"` in `command` for cron-style.
- `WATCHTOWER_CLEANUP=true` — remove old images after update.
- `WATCHTOWER_LABEL_ENABLE=false` — if `true`, only containers with label `com.centurylinklabs.watchtower.enable=true` are updated.
- **HTTP API (manual updates)** — Compose enables `WATCHTOWER_HTTP_API_UPDATE`, `WATCHTOWER_HTTP_API_PERIODIC_POLLS`, and `WATCHTOWER_HTTP_API_PORT=80` so Caddy can reach the API on port 80. Set `WATCHTOWER_HTTP_API_TOKEN` in `stack.env` (required; copy from `stack.env.example` if needed). Example: `curl -X POST -H "Authorization: Bearer <token>" https://watchtower.example.com/v1/update` (or your internal host). Docs: [HTTP API](https://watchtower.nickfedor.com/v1.12.3/advanced-features/http-api/).
- **Prometheus metrics** — `WATCHTOWER_HTTP_API_METRICS=true` exposes `GET /v1/metrics` (same port and Bearer token). Wire-up: `stacks/prometheus/prometheus.yml.example` includes a `watchtower` scrape job; create `~/.config/prometheus/rules/watchtower_bearer_token` with the same token (see `stacks/prometheus/watchtower_bearer_token.example` and [Prometheus README](../prometheus/README.md)). Docs: [Metrics](https://watchtower.nickfedor.com/v1.12.3/advanced-features/metrics/).

**Update only selected containers:** Set `WATCHTOWER_LABEL_ENABLE=true` in this stack, and add to each service you want updated:

```yaml
labels:
  - "com.centurylinklabs.watchtower.enable=true"
```

## Troubleshooting

**"Client version 1.25 is too old. Minimum supported API version is 1.44"** — The old containrrr image is incompatible with Docker 29+. This stack uses the maintained fork `nickfedor/watchtower` (Docker API 1.43+). If the error persists: `docker compose pull && docker compose up -d --force-recreate`.

## Start

`docker compose up -d` from this directory.
