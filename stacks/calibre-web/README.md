# Calibre-Web

Web UI for an existing Calibre library: browse, read, and download eBooks. Uses your Calibre database (`metadata.db`) and book files. Supports OPDS, optional ebook conversion (Docker mod), and Google OAuth.

**Homepage:** https://github.com/janeczku/calibre-web  
**Docker (LinuxServer):** https://docs.linuxserver.io/images/docker-calibre-web  

Access via Caddy at **https://calibre-web.yourdomain.com** (or your configured hostname).

## Quick start

1. Copy `stack.env.example` → `stack.env` (optional: set `PUID`/`PGID` if you bind-mount a library).
2. From the stack directory: `docker compose up -d`.
3. Open the web UI. On first run you’ll be asked for the Calibre database path: set **/books** (or the path where your `metadata.db` lives inside the container).
4. Default login: **admin** with the image’s default password — change immediately in Admin → Edit user.

If you already have a Calibre library on the host, bind-mount it in `docker-compose.yml` (see **Library** below).

**Portainer:** Add stack → paste `docker-compose.yml` → set env vars from `stack.env` if needed → deploy.

## Library

By default the stack uses a named volume `calibre_web_books` for `/books`. To use an existing Calibre library, replace it with a bind mount:

```yaml
volumes:
  - /path/to/your/calibre/library:/books
```

The directory must contain `metadata.db` and your book files. On first setup in the UI, set the database path to **/books**.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `calibre-web:8083`) |
| **Network** | `monitor` |
| **Images** | `lscr.io/linuxserver/calibre-web:latest` |
| **Storage** | Named volumes: `calibre_web_config` (app DB, settings), `calibre_web_books` (Calibre library); or bind-mount `/books` |

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
