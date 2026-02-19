# Mealie

Self-hosted recipe manager and meal planner: import recipes from URLs, plan meals, generate shopping lists, and organize cookbooks.

**Website:** https://mealie.io  
**GitHub:** https://github.com/mealie-recipes/mealie

## Quick start

1. **Environment**
   - Copy `.env.example` to `.env`.
   - If using Caddy (or another reverse proxy), set `BASE_URL` to your full Mealie URL (e.g. `https://mealie.yourdomain.com`).
   - Set `ALLOW_SIGNUP=true` only until you create your account, then set to `false`.
   - Set `TZ` if different from America/Denver.
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer and set the same vars in the stack Environment).
3. **First run:** Open the web UI via Caddy, create your account, then set `ALLOW_SIGNUP=false` and redeploy.

The stack uses a **named volume** `mealie_data` so it works when deployed from Portainer's web editor.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `mealie:9000`) |
| **Network** | `monitor` (external) — Caddy can reverse-proxy to `mealie:9000` |
| **Image** | ghcr.io/mealie-recipes/mealie:latest |
| **Env** | `BASE_URL` recommended when behind HTTPS; `ALLOW_SIGNUP`; optional `DB_ENGINE` (sqlite/postgres) |
| **Storage** | Named volume: `mealie_data` (SQLite DB, uploads, backups) |

## Caddy

Point your Caddy vhost at `http://mealie:9000`. Set `BASE_URL` to your public URL so login and API calls work correctly.

## Optional: PostgreSQL

For PostgreSQL, set `DB_ENGINE=postgres` and add `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_DB`, plus a postgres service and volume. See [Mealie backend config](https://docs.mealie.io/documentation/getting-started/installation/backend-config/) for details.
