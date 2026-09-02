# Calibre-Web

Web UI for an existing Calibre library: browse, read, and download eBooks. Uses your Calibre database (`metadata.db`) and book files. Supports OPDS, optional ebook conversion (Docker mod), and Google OAuth.

**Homepage:** https://github.com/janeczku/calibre-web
**Docker (LinuxServer):** https://docs.linuxserver.io/images/docker-calibre-web

Access via Caddy at **https://calibre-web.yourdomain.com** (or your configured hostname).

## Quick start

1. Copy `stack.env.example` → `stack.env`, set `CALIBRE_BOOKS_PATH`, and optionally set `PUID`/`PGID`.
2. From the stack directory: `docker compose up -d`.
3. Open the web UI. On first run you'll be asked for the Calibre database path: set **/books** (or the path where your `metadata.db` lives inside the container).
4. Default login: **admin** with the image's default password, change immediately in Admin → Edit user.

**Portainer:** Add stack → paste `docker-compose.yml` → set env vars from `stack.env` if needed → deploy.

## Library

`CALIBRE_BOOKS_PATH` is bind-mounted at `/books` and defaults to
`/mnt/unraid/media/books`. The directory must contain `metadata.db` and your
book files. On first setup in the UI, set the database path to **/books**.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `calibre-web:8083`) |
| **Network** | `ingress-public` for dedicated Caddy-to-service traffic |
| **Images** | `lscr.io/linuxserver/calibre-web:latest` |
| **Storage** | `calibre_web_config` (app DB and settings), `${CALIBRE_BOOKS_PATH}` → `/books` |

## Caddy reverse proxy

Add a site block for the Calibre-Web hostname (e.g. `calibre-web.yourdomain.com`):

```
calibre-web.yourdomain.com {
	reverse_proxy calibre-web:8083
}
```

## Health and monitoring

Calibre-Web does not expose a dedicated health endpoint. Use a generic HTTP check to the app URL (e.g. `https://calibre-web.yourdomain.com`) in Uptime Kuma.

## Optional: ebook conversion

For in-app conversion (e.g. EPUB to PDF), add to `stack.env` (x86-64 only):

```
DOCKER_MODS=linuxserver/mods:universal-calibre
```

Then in Calibre-Web Admin → Basic Configuration → External Binaries, set the path to Calibre E-book converter to `/usr/bin/` (directory) or `/usr/bin/ebook-convert` as per LinuxServer docs.
