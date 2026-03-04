# ArchiveBox

Self-hosted web archive: save full copies of web pages (HTML, screenshots, PDFs, and WARCs) from URLs, bookmarks, and feeds.

**Website:** https://archivebox.io  
**Docs:** https://github.com/ArchiveBox/ArchiveBox/wiki  
**GitHub:** https://github.com/ArchiveBox/ArchiveBox  
**Docker image:** https://hub.docker.com/r/archivebox/archivebox  
**Releases:** https://github.com/ArchiveBox/ArchiveBox/releases  

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `SEARCH_BACKEND_PASSWORD` (see **Secrets** below).
   - Optionally set `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` to match your Caddy hostnames.
2. **Deploy:** `docker compose --env-file stack.env up -d` (or add the stack in Portainer and set the same vars in the stack Environment).
3. **Access:** Open via Caddy (e.g. `https://archivebox.home` or `https://archivebox.yourdomain.com`).
4. **Add URLs:** Use the UI, or run CLI commands such as:
   - `docker compose run archivebox add 'https://example.com'`
   - `docker compose run archivebox add --depth=1 'https://news.ycombinator.com'`

The stack includes:

- `archivebox` – main web UI and archiver.
- `archivebox_scheduler` – optional scheduler container that runs background jobs.
- `sonic` – fast full-text search backend.

All state is stored in the `archivebox-data` and `archivebox-sonic-data` named volumes.

## Secrets

Generate strong secrets before exposing ArchiveBox publicly:

```bash
# Admin password (set ADMIN_PASSWORD)
openssl rand -base64 32

# Sonic search backend password (set SEARCH_BACKEND_PASSWORD)
openssl rand -hex 24
```

Set the outputs in `stack.env` or in the Portainer stack Environment.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `archivebox:8000`) |
| **Network** | `monitor` (external) — Caddy reverse-proxies to `archivebox:8000` |
| **Images** | `archivebox/archivebox:latest`, `archivebox/sonic:latest` |
| **Env (required)** | `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SEARCH_BACKEND_PASSWORD` |
| **Env (recommended)** | `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` when exposed via Caddy |
| **Env (optional)** | `PUBLIC_INDEX`, `PUBLIC_SNAPSHOTS`, `PUBLIC_ADD_VIEW`, plus additional ArchiveBox options (see docs) |
| **Storage** | Named volumes: `archivebox-data` (ArchiveBox data), `archivebox-sonic-data` (Sonic index) |

## Caddy reverse proxy

Example Caddy vhosts (add to your `Caddyfile`):

```caddy
archivebox.home, archivebox.local {
	tls internal
	reverse_proxy archivebox:8000
}

archivebox.yourdomain.com {
	tls {
		dns cloudflare {env.CLOUDFLARE_API_TOKEN}
	}
	reverse_proxy archivebox:8000
}
```

Ensure the stack is on the `monitor` network so Caddy can reach `archivebox:8000`.

## Start

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose and set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SEARCH_BACKEND_PASSWORD` (and optional vars) in **Environment**.

