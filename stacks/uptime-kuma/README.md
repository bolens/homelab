# Uptime Kuma

Self-hosted uptime monitoring and status page. Monitors HTTP(s), TCP, ping, and more; supports many notification channels (Telegram, email, Discord, etc.).

**Website:** https://uptime.kuma.pet  
**Docs:** https://github.com/louislam/uptime-kuma/wiki  
**GitHub:** https://github.com/louislam/uptime-kuma  
**Docker image:** https://hub.docker.com/r/louislam/uptime-kuma  
**Releases:** https://github.com/louislam/uptime-kuma/releases  

## Quick start

1. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer).
2. Open via Caddy (e.g. https://kuma.home or https://status.yourdomain.com) and create the admin account. No host port is exposed; Caddy reaches `uptime-kuma:3001` through `proxy-ingress`.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `uptime-kuma:3001`) |
| **Volume** | `uptime_kuma_data` (persistent data) |
| **Network** | `proxy-ingress` for Caddy; `mail-services` for SMTP; private `docker-api` for container metadata |
| **Env** | See [ENV-VARS.md](../../documents/ENV-VARS.md) and [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) for TZ/locale and shared resources. |

Docker container monitors connect to
`tcp://uptime-kuma-docker-socket-proxy:2375` over a private internal network.
The proxy permits container inspection but blocks Docker API mutations.

### Email notifications

To send downtime alerts via email, add an **Email** notification in Uptime Kuma (Settings → Notifications). Use the shared **postfix** SMTP relay: host `smtp-relay`, port `587`, STARTTLS over `mail-services`. For **internal-only** (no external delivery), deploy the **mailpit** stack and set Postfix `RELAYHOST=mailpit:1025`; all alerts will appear in the Mailpit web UI. See [stacks/postfix/README.md](../postfix/README.md) and [stacks/mailpit/README.md](../mailpit/README.md).

### ntfy push notifications

Uptime Kuma has native ntfy support. To enable:

1. Settings → Notifications → Add Notification → **ntfy**
2. ntfy Server URL: use the public HTTPS ntfy endpoint.
3. Topic: `uptime-kuma` (or any topic you subscribe to in the ntfy app)
4. Priority: High for down alerts, default for recovery
5. Save and test — you should receive a push notification immediately.

The ntfy stack is at `stacks/ntfy`; the public URL is `https://ntfy.example.com`.

**Monitoring targets:** use public or Tailscale HTTPS endpoints. Internal Docker-name checks are intentionally handled by Prometheus and the observability stack.

## Troubleshooting

**Caddy access fails:**

1. Confirm Caddy and Uptime Kuma share `proxy-ingress`.
2. From Caddy, verify `http://uptime-kuma:3001` responds.
3. Configure monitors with their HTTPS URLs.

## Start

`docker compose up -d` from this directory.
