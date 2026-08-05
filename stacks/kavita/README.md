# Kavita

Comics, manga, and eBook server with a built-in web reader, OPDS support, and reading progress. Single app for mixed libraries (CBZ, CBR, EPUB, etc.). Can run alongside Komga and Calibre-Web or replace one of them depending on preference.

**Homepage:** https://www.kavitareader.com  
**GitHub:** https://github.com/Kareadita/Kavita  
**Docker (LinuxServer):** https://docs.linuxserver.io/images/docker-kavita  

Access via Caddy at **https://kavita.yourdomain.com** (or your configured hostname).

## Quick start

1. Copy `stack.env.example` → `stack.env`; set the library paths and optionally `PUID`, `PGID`, and `TZ`.
2. From the stack directory: `docker compose up -d`.
3. Open the web UI and add libraries pointing at `/data/books` and `/data/comics`.

**Portainer:** Add stack → paste `docker-compose.yml` → set env vars → deploy.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `kavita:5000`) |
| **Network** | `monitor` |
| **Images** | `lscr.io/linuxserver/kavita:latest` |
| **Storage** | `kavita_config`, `${KAVITA_BOOKS_PATH}` → `/data/books`, `${KAVITA_COMICS_PATH}` → `/data/comics` |

## Caddy reverse proxy

Add a site block for the Kavita hostname (e.g. `kavita.yourdomain.com`):

```
kavita.yourdomain.com {
	reverse_proxy kavita:5000
}
```

## Health and monitoring

Kavita does not expose a dedicated health endpoint. Use a generic HTTP check to the app URL (e.g. `https://kavita.yourdomain.com`) in Uptime Kuma.
