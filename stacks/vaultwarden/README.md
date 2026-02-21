# Vaultwarden

Lightweight, self-hosted password manager compatible with Bitwarden clients (browser extensions, mobile apps, CLI).

**Website:** https://vaultwarden.github.io  
**GitHub:** https://github.com/dani-garcia/vaultwarden

## Quick start

1. **Environment**
   - Copy `.env.example` to `.env`.
   - If using Caddy (or another reverse proxy), set `DOMAIN=https://vault.yourdomain.com`.
   - Set `SIGNUPS_ALLOWED=true` only until you create your account, then set to `false`.
   - (Optional) To enable the admin panel at `/admin`, set `ADMIN_TOKEN`. Generate with: `openssl rand -base64 48`.
   - Set `TZ` if different from America/Denver.
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer and set the same vars in the stack Environment).
3. **First run:** Open the web UI via Caddy, create your account, then set `SIGNUPS_ALLOWED=false` and redeploy.

The stack uses a **named volume** `vw_data` so it works when deployed from Portainer’s web editor.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `vaultwarden:80`) |
| **Network** | `monitor` (external) — Caddy can reverse-proxy to `vaultwarden:80` |
| **Image** | vaultwarden/server (Docker Hub) |
| **Env** | `DOMAIN` recommended when behind HTTPS; `SIGNUPS_ALLOWED`; optional `ADMIN_TOKEN`, `WEBSOCKET_ENABLED` |
| **Storage** | Named volume: `vw_data` (SQLite DB and attachments) |

## Caddy

Point your Caddy vhost at `http://vaultwarden:80` and enable WebSocket support if you use the browser extension or desktop app. Set `DOMAIN` to your public URL so attachments and WebSocket work correctly.

## Clients

Use official Bitwarden apps and extensions; set the server URL to your Vaultwarden instance (e.g. `https://vault.yourdomain.com`).
