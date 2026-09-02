# Komga

Self-hosted comics and manga server: organize, browse, and read CBZ, CBR, PDF, and EPUB in the browser. OPDS support for apps like Tachiyomi; multi-user with reading progress and library-level permissions.

**Homepage:** https://komga.org  
**Docs:** https://komga.org/docs  
**GitHub:** https://github.com/gotson/komga  
**Docker:** https://hub.docker.com/r/gotson/komga  

Access via Caddy at **https://komga.yourdomain.com** (or your configured hostname).

## Quick start

1. Copy `stack.env.example` → `stack.env`; confirm the comic and manga paths. Set `JAVA_TOOL_OPTIONS` only if the library needs a larger JVM heap.
2. From the stack directory: `docker compose up -d`.
3. Open the web UI, create the first user, then add separate libraries rooted at `/data/comics` and `/data/manga`.

**Portainer:** Add stack → paste `docker-compose.yml` → set env vars from `stack.env` if needed → deploy.

## Library

The shared libraries are mounted read-only. Mylar3 can organize `/data/comics`
through its own writable media mount; Komga scans the same host directory
without modifying it. Keep `/config` on the local `komga_config` volume because
Komga does not support its database on NFS or CIFS. Library roots must not
overlap, so use `/data/comics` and `/data/manga`, never `/data`.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `komga:25600`) |
| **Network** | `ingress-public` for dedicated Caddy-to-service traffic |
| **Images** | `gotson/komga:latest` |
| **Storage** | Local `komga_config`; `${KOMGA_COMICS_PATH}` → `/data/comics` and `${KOMGA_MANGA_PATH}` → `/data/manga`, both read-only |

## Caddy reverse proxy

Add a site block for the Komga hostname (e.g. `komga.yourdomain.com`):

```
komga.yourdomain.com {
	reverse_proxy komga:25600
}
```

## Health and monitoring

Komga does not expose a dedicated health endpoint. Use a generic HTTP check to the app URL (e.g. `https://komga.yourdomain.com`) in Uptime Kuma.
