# Uptime Kuma

Self-hosted uptime monitoring and status page. Monitors HTTP(s), TCP, ping, and more; supports many notification channels (Telegram, email, Discord, etc.).

**Website:** https://uptime.kuma.pet  
**Docs:** https://github.com/louislam/uptime-kuma/wiki  
**GitHub:** https://github.com/louislam/uptime-kuma  
**Docker image:** https://hub.docker.com/r/louislam/uptime-kuma  
**Releases:** https://github.com/louislam/uptime-kuma/releases  

## Quick start

1. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer).
2. Open via Caddy (e.g. https://kuma.home or https://status.yourdomain.com) and create the admin account. No host port is exposed; Caddy reaches `uptime-kuma:3001` through `ingress-admin`.

## Upgrading from v1

Before the first v2 start, stop the stack and back up the complete
`uptime_kuma_data` volume. The initial v2 startup migrates the database and can
take several minutes or longer. Follow the container logs and do not interrupt
the migration; if it is interrupted, restore the backup before retrying.

Badge URLs that specify `:duration` must use an explicit unit in v2, such as
`24h`, `30d`, or `1y`.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `uptime-kuma:3001`) |
| **Volume** | `uptime_kuma_data` (persistent data) |
| **Network** | `ingress-admin` for Caddy; `mail-clients` for SMTP; private `docker-api` for container metadata |
| **Env** | See [ENV-VARS.md](../../documents/ENV-VARS.md) and [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) for TZ/locale and shared resources. |

Docker container monitors connect to
`tcp://uptime-kuma-docker-socket-proxy:2375` over a private internal network.
The proxy permits container inspection but blocks Docker API mutations.

### Monitoring baseline

The managed baseline is in
[`scripts/uptime-kuma-baseline.sql.example`](../../scripts/uptime-kuma-baseline.sql.example).
It configures:

- 90-day heartbeat retention.
- Two retries at 30-second intervals, a 15-second timeout, and 30-minute
  reminder intervals.
- 30-second checks for critical public services; 60 seconds for other checks.
- Public HTTPS monitors for services that should be reachable through Caddy.
- A `Critical Containers` group using the read-only Docker socket proxy.
- `Homelab ntfy` as the default notification for active non-group monitors.

The baseline can be reapplied while Uptime Kuma is stopped:

```bash
docker run --rm --entrypoint sqlite3 \
  -v uptime-kuma_uptime_kuma_data:/app/data \
  louislam/uptime-kuma:2 \
  /app/data/kuma.db < ../../scripts/uptime-kuma-baseline.sql.example
```

### Notifications

`Homelab ntfy` publishes to the `uptime-kuma` topic at
`https://ntfy.bolens.dev`. `Homelab SMTP` is the fallback and uses
`smtp-relay:587` over `mail-clients`; its sender and recipient match the DIUN
mail notification settings. Test both integrations from **Settings →
Notifications** after changing either service.

Public service checks use HTTPS through Caddy. Container state checks use the
restricted Docker socket proxy and complement, rather than replace, Prometheus
metrics and alerting.

### Database maintenance

Keep backups outside the live Docker volume. Stop Uptime Kuma before copying or
vacuuming `kuma.db`, run `PRAGMA quick_check`, and retain the compressed backup
until the restarted service and monitors have been verified.

### Status pages

The managed status-page and dashboard-group baseline is in
[`scripts/uptime-kuma-status-pages.sql.example`](../../scripts/uptime-kuma-status-pages.sql.example).
It creates three non-indexed public pages:

- `https://status.bolens.dev/status/services` for user-facing services.
- `https://status.bolens.dev/status/media` for streaming, libraries, and media
  automation.
- `https://status.bolens.dev/status/infrastructure` for public edge, identity, observability, and
  developer-platform endpoints.

The pages intentionally omit Docker, database, and other private implementation
details. Monitor URLs are not published as links. The root
`https://status.bolens.dev/` redirects to the services page; the administrative
UI remains available at `https://kuma.bolens.dev/`.

Each page has an RSS title configured for incident subscriptions. Before
planned work, create a maintenance window in **Maintenance → Schedule
Maintenance**, select only the affected monitors, and publish the notice to the
relevant status page. Close the window after verification rather than muting
notification integrations globally.

### Functional checks

Landing-page checks use application health endpoints where available, including
Authentik, Gitea, Harbor, Jellyfin, MinIO, Navidrome, Nextcloud, and Seafile.
SMTP submission is checked directly on `smtp-relay:587`. AdGuard Home, Pi-hole,
and Unbound are represented by Docker monitors whose container health checks
perform local DNS resolution.

Restic uses a push monitor with a 26-hour grace period. Its success, incomplete,
and failure callbacks travel only over the internal `monitoring-push` network;
the backup network remains isolated. The first successful scheduled backup
replaces the initialization heartbeat.

## Troubleshooting

**Caddy access fails:**

1. Confirm Caddy and Uptime Kuma share `ingress-admin`.
2. From Caddy, verify `http://uptime-kuma:3001` responds.
3. Configure monitors with their HTTPS URLs.

## Start

`docker compose up -d` from this directory.
