# Watchtower

Automatically updates running containers when new images are available. Uses the Docker socket on the host.

## Quick start

`docker compose up -d` from this directory (or deploy as a stack in Portainer). By default: polls every 24 hours and removes old images after updating.

## Configuration

| Item | Details |
|------|---------|
| **Volume** | `/var/run/docker.sock` (required) |
| **Env** | See [ENV-VARS.md](../ENV-VARS.md) for TZ/locale. |

**Key env vars (in `docker-compose.yml`):**

- `WATCHTOWER_POLL_INTERVAL=86400` — check every 24h. Override or use `--schedule "0 0 3 * * *"` in `command` for cron-style.
- `WATCHTOWER_CLEANUP=true` — remove old images after update.
- `WATCHTOWER_LABEL_ENABLE=false` — if `true`, only containers with label `com.centurylinklabs.watchtower.enable=true` are updated.

**Update only selected containers:** Set `WATCHTOWER_LABEL_ENABLE=true` in this stack, and add to each service you want updated:

```yaml
labels:
  - "com.centurylinklabs.watchtower.enable=true"
```

## Troubleshooting

**"Client version 1.25 is too old. Minimum supported API version is 1.44"** — Docker daemon is newer than the image’s client. Pull latest and recreate: `docker pull containrrr/watchtower:latest` then redeploy. See [Watchtower releases](https://github.com/containrrr/watchtower/releases) for API compatibility.

## Start

`docker compose up -d` from this directory.
