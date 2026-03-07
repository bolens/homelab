# Portainer CE

Docker management UI: manage containers, images, volumes, and stacks from a web interface.

## Quick start

1. If you access Portainer through Caddy or another reverse proxy (e.g. `https://portainer.yourdomain.com`), copy `stack.env.example` → `stack.env` and set `TRUSTED_ORIGINS` to the **hostname only** (e.g. `portainer.yourdomain.com` — no `https://` or port). Otherwise you may get **"Forbidden - Invalid origin"** when deploying or logging in.
2. `docker compose up -d` from this directory (or deploy as a stack). Open https://localhost:9443 (or your Caddy URL) and complete the initial admin setup.

## Configuration

| Item | Details |
|------|---------|
| **Port** | 9443 (HTTPS only) |
| **Volumes** | Docker socket (required), `portainer_data` (persistent) |
| **Network** | `monitor` (so Caddy can reverse-proxy to `portainer:9443`) |
| **Security** | `no-new-privileges:true` |
| **Behind proxy** | Set `TRUSTED_ORIGINS` to the hostname only, e.g. `portainer.yourdomain.com` (see `stack.env.example`) |

Access via Caddy (e.g. `https://portainer.yourdomain.com`) or Cloudflare Tunnel once those stacks are configured.

### "Forbidden - Invalid origin" when deploying stacks

If you use Portainer through a reverse proxy (Caddy, Cloudflare Tunnel, etc.), set **TRUSTED_ORIGINS** to the **hostname only** (e.g. `portainer.yourdomain.com` — no `https://` or port).

- **If Portainer is already running:** In Portainer go to **Stacks** → open the stack that runs Portainer (or **Containers** → Portainer → **Duplicate/Edit**) → add an environment variable: name `TRUSTED_ORIGINS`, value `portainer.yourdomain.com` (hostname only) → **Update the stack** or recreate the container. Then reload the Portainer UI.
- **If you deploy Portainer from CLI:** Copy `stack.env.example` → `stack.env`, set `TRUSTED_ORIGINS=portainer.yourdomain.com`, then `docker compose up -d`.

## Start

`docker compose up -d` from this directory.
