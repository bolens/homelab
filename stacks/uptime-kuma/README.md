# Uptime Kuma

Self-hosted uptime monitoring and status page. Monitors HTTP(s), TCP, ping, and more; supports many notification channels (Telegram, email, Discord, etc.).

**Website:** https://uptime.kuma.pet  
**Docs:** https://github.com/louislam/uptime-kuma/wiki  
**GitHub:** https://github.com/louislam/uptime-kuma  
**Docker image:** https://hub.docker.com/r/louislam/uptime-kuma  
**Releases:** https://github.com/louislam/uptime-kuma/releases  

## Quick start

1. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer).
2. Open via Caddy (e.g. https://kuma.home or https://status.yourdomain.com) and create the admin account. No host port is exposed; the stack attaches to the `monitor` network for Caddy to reverse-proxy to `uptime-kuma:3001`.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `uptime-kuma:3001`) |
| **Volume** | `uptime_kuma_data` (persistent data) |
| **Network** | `monitor` — shared with Caddy for internal checks |
| **Env** | See [ENV-VARS.md](../../documents/ENV-VARS.md) and [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) for TZ/locale and shared resources. |

### Email notifications

To send downtime alerts via email, add an **Email** notification in Uptime Kuma (Settings → Notifications). Use the shared **postfix** SMTP relay: host `smtp-relay`, port `587`, STARTTLS. No username/password needed when both stacks are on the `monitor` network. For **internal-only** (no external delivery), deploy the **mailpit** stack and set Postfix `RELAYHOST=mailpit:1025`; all alerts will appear in the Mailpit web UI. See [stacks/postfix/README.md](../postfix/README.md) and [stacks/mailpit/README.md](../mailpit/README.md).

**Monitoring targets:**

- **Containers on `monitor` network (Caddy, self):** Use service names. Examples: Caddy → `http://caddy:80`, self → `http://uptime-kuma:3001`. HTTP, no SSL verify for HTTP targets.
- **Loki / Promtail (no Caddy):** Add HTTP monitors with **URL** `http://loki:3100/ready` and `http://promtail:9080/ready`. Leave “Verify SSL” off. Both are internal-only; Uptime Kuma reaches them over the `monitor` network.
- **Host services (e.g. Portainer):** Use `https://host.docker.internal:9443` (disable “Verify SSL” if using self-signed).

The `monitor` network is created when you deploy Caddy or Uptime Kuma; the other stack attaches to it. No manual `docker network create` needed.

## Troubleshooting

**Caddy heartbeat fails:**

1. Confirm both on `monitor`: `docker network inspect monitor --format '{{range .Containers}}{{.Name}} {{end}}'` → should list `caddy` and `uptime-kuma`.
2. From container: `docker exec uptime-kuma wget -qO- --timeout=2 http://caddy:80 | head -1` → should return Caddy’s response.
3. In Uptime Kuma: URL = `http://caddy:80`, no keyword, “Verify SSL” off.

## Start

`docker compose up -d` from this directory.
