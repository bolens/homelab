# Diun

Docker image update notifier. Watches your running containers’ images and sends a notification when new tags are available (e.g. Telegram, Discord, webhook). Complements Watchtower: you see what changed before or after Watchtower pulls. No web UI; no Caddy reverse proxy needed.

## Quick start

1. Copy `.env.example` → `.env` and set at least one notifier (e.g. `DIUN_NOTIF_TELEGRAM_TOKEN` and `DIUN_NOTIF_TELEGRAM_CHATIDS`).
2. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer and add the env vars in the stack).
3. Check logs: `docker compose logs -f diun`.

## Configuration

| Item | Details |
|------|---------|
| **Volumes** | `diun_data` (bbolt DB for image manifests), Docker socket (read-only). |
| **Env** | See [ENV-VARS.md](../../documents/ENV-VARS.md) for TZ/locale. Diun-specific: schedule, notifiers (see below). |
| **Schedule** | Default `0 */6 * * *` (every 6 hours). Override `DIUN_WATCH_SCHEDULE` (cron). |

### Notifiers (env vars)

- **Telegram:** `DIUN_NOTIF_TELEGRAM_TOKEN` (from @BotFather), `DIUN_NOTIF_TELEGRAM_CHATIDS` (comma-separated).
- **Discord:** `DIUN_NOTIF_DISCORD_WEBHOOKURL`.
- **Webhook / Mail / Slack / Gotify / ntfy / etc.:** See [Diun config](https://crazymax.dev/diun/config/) and [notifiers](https://crazymax.dev/diun/config/notif/).

### Watch only selected containers

By default Diun watches all containers. To watch only stacks you care about:

1. Set `DIUN_PROVIDERS_DOCKER_WATCHBYDEFAULT=false` in this stack’s env.
2. Add to each service you want to watch: `labels: - "diun.enable=true"`.

## Start

`docker compose up -d` from this directory.
