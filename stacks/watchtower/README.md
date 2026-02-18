# Watchtower

Auto-updates running Docker containers when new images are available.

- **Schedule:** every 24 hours (override with `WATCHTOWER_POLL_INTERVAL` or use `--schedule` in `command`).
- **Cleanup:** old images are removed after updates.

To update only specific containers:

1. Add this label to each service you want Watchtower to update:

```yaml
labels:
  - "com.centurylinklabs.watchtower.enable=true"
```

2. In this stack's `docker-compose.yml`, set `WATCHTOWER_LABEL_ENABLE: "true"`.

**"Client version 1.25 is too old. Minimum supported API version is 1.44":** Your Docker daemon (v29+) requires API 1.44; Watchtower's image may ship an older client. Pull the latest image and redeploy: `docker pull containrrr/watchtower:latest` then recreate the container. If it still fails, check [Watchtower releases](https://github.com/containrrr/watchtower/releases) for a build that supports Docker API 1.44+.

**Start:** `docker compose up -d` (from this directory or via Portainer).
