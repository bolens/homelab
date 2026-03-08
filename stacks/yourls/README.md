# YOURLS (Your Own URL Shortener)

Self-hosted URL shortener: one app with web UI, API, and redirects. No path routing—Caddy just reverse-proxies the host to the container.

**Website:** https://yourls.org  
**Docs:** https://docs.yourls.org  
**GitHub:** https://github.com/YOURLS/YOURLS  
**Docker image:** https://hub.docker.com/_/yourls  
**Releases:** https://github.com/YOURLS/YOURLS/releases  

The stack uses the official image `yourls:1.10.3-apache` by default. Override `YOURLS_IMAGE` in `stack.env` only if you use your own build (e.g. private registry).

## Quick start

1. **Environment**
   - Run `./prepare-stack.sh` (or copy `stack.env.example` to `stack.env`).
   - Set `YOURLS_SITE` to the **bare URL** of the shortener (e.g. `https://urls.yourdomain.com`). Must match the Caddy hostname. The vhost serves the dashboard at `/` and short links stay at root (e.g. `https://urls.yourdomain.com/abc`).
   - Set `YOURLS_USER` and `YOURLS_PASS` (admin login for the web UI).
   - Generate and set the required secrets (see **Generating keys and secrets** below).
2. **Config dir (vhost + proxy-https-fix):** Run `./prepare-stack.sh` to create `~/.config/yourls/` and copy `vhost.conf.example` and `proxy-https-fix.php.example` there as `vhost.conf` and `proxy-https-fix.php`. The stack mounts this dir so the image gets the DirectoryIndex fix and PHP sees HTTPS behind Caddy. Override with `YOURLS_CONFIG_DIR` in `stack.env` (absolute path for Portainer). If you see **ERR_TOO_MANY_REDIRECTS**, re-run prepare-stack or re-copy the examples and restart the container; see [TROUBLESHOOTING.md](../../documents/TROUBLESHOOTING.md).
3. **Deploy:** `docker compose --env-file stack.env up -d` so Compose reads your env (avoids "variable is not set" warnings and substitutes `YOURLS_CONFIG_DIR` correctly). Or add the stack in Portainer with the same env.
4. **Access:** Open via Caddy (e.g. https://urls.yourdomain.com). Log in with `YOURLS_USER` / `YOURLS_PASS`, create short links.

## Generating keys and secrets

Run these and set the outputs in `stack.env`:

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
| **Images** | `yourls:1.10.3-apache`, `mariadb:11` (override `YOURLS_IMAGE` if you use your own) |
| **Env** | `YOURLS_SITE`, `YOURLS_USER`, `YOURLS_PASS`, `YOURLS_COOKIEKEY`, `YOURLS_DB_*` (see `stack.env.example`) |
| **Storage** | `yourls_data` (user config/plugins), `yourls_db_data` (MariaDB) |
| **Config dir** | `vhost.conf` and `proxy-https-fix.php` in `~/.config/yourls` (run `./prepare-stack.sh` or copy from `*.example`); override with `YOURLS_CONFIG_DIR` in `stack.env` (absolute path for Portainer) |

## Caddy reverse proxy

Example (hostnames must match `YOURLS_SITE`; include `urls.` so YOURLS is at e.g. https://urls.yourdomain.com):

```
urls.yourdomain.com, short.yourdomain.com, s.yourdomain.com {
  reverse_proxy yourls:8080 {
    header_up X-Forwarded-Proto https
  }
}
```

Ensure the stack is on the `monitor` network so Caddy can reach `yourls:8080`.

## Start

From this directory: `docker compose --env-file stack.env up -d` (compose only auto-loads `.env`; `stack.env` has your secrets).  
In Portainer: deploy the stack from Git and set the required env vars (and `YOURLS_CONFIG_DIR` to the absolute path to your config dir containing `vhost.conf` and `proxy-https-fix.php`).
