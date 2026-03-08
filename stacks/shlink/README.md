# Shlink

Self-hosted **URL shortener**: short links, redirects, REST API, visit analytics, and optional geolocation. Use the web UI at [app.shlink.io](https://app.shlink.io) (add your server URL and API key) or self-host the web client. Separate from YOURLS (which lives at `urls.yourdomain.com` in this repo); Shlink is at `short.yourdomain.com`.

**Website:** https://shlink.io  
**Docs:** https://shlink.io/documentation  
**GitHub:** https://github.com/shlinkio/shlink  
**Docker image:** https://hub.docker.com/r/shlinkio/shlink  

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `DEFAULT_DOMAIN` to your short-domain hostname (no `https://`), e.g. `short.yourdomain.com`. Must match the Caddy hostname.
   - Set `IS_HTTPS_ENABLED=true` (default) when behind Caddy with HTTPS.
   - Set `GEOLITE_LICENSE_KEY` (get a free key at [MaxMind GeoLite2](https://www.maxmind.com/en/geolite2/signup)). Shlink works without it but geolocation will be disabled.
   - Optional: set `INITIAL_API_KEY` to a generated key (e.g. `openssl rand -hex 32`), or leave empty and create one after first run: `docker exec shlink shlink api-key:generate`.
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer and set the same vars).
3. **Access:** Open via Caddy at `https://short.yourdomain.com`. Use [app.shlink.io](https://app.shlink.io) to manage short URLs: add server URL `https://short.yourdomain.com` and the API key.

The stack uses an internal SQLite DB by default (volume `shlink_data`). For production with multiple instances or shared locks, consider an external DB (MariaDB/PostgreSQL) and optional Redis; see [Shlink docs](https://shlink.io/documentation/install-docker-image).

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `shlink:8080`) |
| **Network** | `monitor` (external) — Caddy can reach `shlink:8080` |
| **Image** | `shlinkio/shlink:stable` (override with `SHLINK_IMAGE` in `stack.env`) |
| **Env** | `DEFAULT_DOMAIN`, `IS_HTTPS_ENABLED`, `GEOLITE_LICENSE_KEY` (required); optional `INITIAL_API_KEY`, `TRUSTED_PROXIES` (use `2` when behind Caddy + Cloudflare Tunnel; see `stack.env.example`) |
| **Storage** | `shlink_data` (SQLite DB and data). For external DB, see commented block in `docker-compose.yml`. |

## Caddy reverse proxy

The repo’s `Caddyfile.example` already includes a block for `short.yourdomain.com` (and `short.home`, `short.local`) proxying to `shlink:8080` with `header_up X-Forwarded-Proto https`. Ensure the stack is on the `monitor` network.

Example (hostnames must match `DEFAULT_DOMAIN`):

```
short.home, short.yourdomain.com {
  reverse_proxy shlink:8080 {
    header_up X-Forwarded-Proto https
  }
}
```

## API key

If you did not set `INITIAL_API_KEY`, generate one after the first run:

```bash
docker exec shlink shlink api-key:generate
```

Use this key in the [Shlink web client](https://app.shlink.io) when adding your server (URL = `https://short.yourdomain.com`).

## Start

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose, set `DEFAULT_DOMAIN`, `GEOLITE_LICENSE_KEY`, and optional `INITIAL_API_KEY` in **Environment**.
