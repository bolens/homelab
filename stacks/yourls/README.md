# YOURLS (Your Own URL Shortener)

Self-hosted URL shortener: one app with web UI, API, and redirects. No path routing—Caddy just reverse-proxies the host to the container.

**Website:** https://yourls.org  
**Docs:** https://docs.yourls.org  
**GitHub:** https://github.com/YOURLS/YOURLS

## Quick start

1. **Environment**
   - Copy `.env.example` to `.env`.
   - Set `YOURLS_SITE` to the URL you will use in Caddy (e.g. `https://short.home` or `https://short.yourdomain.com`).
   - Set `YOURLS_USER` and `YOURLS_PASS` (admin login for the web UI).
   - Generate and set the required secrets (see **Generating keys and secrets** below).
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer with the same env).
3. **Access:** Open via Caddy (e.g. https://short.home). Log in with `YOURLS_USER` / `YOURLS_PASS`, create short links.

## Generating keys and secrets

Run these and set the outputs in `.env`:

```bash
# YOURLS_COOKIEKEY – cookie auth
openssl rand -hex 32

# YOURLS_DB_PASSWORD and YOURLS_DB_ROOT_PASSWORD – MariaDB (use two different values or one for both)
openssl rand -base64 24
```

Set `YOURLS_COOKIEKEY` to the first output; set `YOURLS_DB_PASSWORD` and `YOURLS_DB_ROOT_PASSWORD` to strong values (e.g. two runs of `openssl rand -base64 24`, or one value for both if acceptable for your setup).

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `yourls:8080`) |
| **Network** | `monitor` (external) — Caddy can reach `yourls:8080` |
| **Images** | `yourls:1.9.2-apache`, `mariadb:11` |
| **Env** | `YOURLS_SITE`, `YOURLS_USER`, `YOURLS_PASS`, `YOURLS_COOKIEKEY`, `YOURLS_DB_*` (see `.env.example`) |
| **Storage** | `yourls_data` (user config/plugins), `yourls_db_data` (MariaDB) |
| **Override** | `Dockerfile` copies `vhost.conf` into the image (adds `DirectoryIndex` so `/` works; no bind mount — works with Portainer/Git deploy) |

## Caddy reverse proxy

Example (same hostnames as `YOURLS_SITE`):

```
short.home, short.yourdomain.com, s.yourdomain.com {
  reverse_proxy yourls:8080
}
```

Ensure the stack is on the `monitor` network so Caddy can reach `yourls:8080`.

## Start

From this directory: `docker compose up -d` (builds the image with the vhost fix).  
In Portainer: deploy the stack from Git; ensure **Build the image** (or equivalent) is enabled so the Dockerfile and `vhost.conf` are used. Set the required env vars in the stack.
