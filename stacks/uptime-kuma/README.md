# Uptime Kuma

Self-hosted uptime monitoring and status page. Monitors HTTP(s), TCP, ping, and more; supports many notification channels (Telegram, email, Discord, etc.).

## Quick start

1. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer).
2. Open http://localhost:3001 (or https://kuma.home once Caddy is up) and create the admin account.

## Configuration

| Item | Details |
|------|---------|
| **Port** | 3001 |
| **Volume** | `uptime_kuma_data` (persistent data) |
| **Network** | `monitor` — shared with Caddy for internal checks |
| **Env** | See [ENV-VARS.md](../ENV-VARS.md) for TZ/locale. |

**Monitoring targets:**

- **Containers on `monitor` network (Caddy, self):** Use service names. Examples: Caddy → `http://caddy:80`, self → `http://uptime-kuma:3001`. HTTP, no SSL verify for HTTP targets.
- **Host services (e.g. Portainer):** Use `https://host.docker.internal:9443` (disable “Verify SSL” if using self-signed).

The `monitor` network is created when you deploy Caddy or Uptime Kuma; the other stack attaches to it. No manual `docker network create` needed.

## Troubleshooting

**Caddy heartbeat fails:**

1. Confirm both on `monitor`: `docker network inspect monitor --format '{{range .Containers}}{{.Name}} {{end}}'` → should list `caddy` and `uptime-kuma`.
2. From container: `docker exec uptime-kuma wget -qO- --timeout=2 http://caddy:80 | head -1` → should return Caddy’s response.
3. In Uptime Kuma: URL = `http://caddy:80`, no keyword, “Verify SSL” off.

## Start

`docker compose up -d` from this directory.
