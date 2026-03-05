# Komga

Self-hosted comics and manga server: organize, browse, and read CBZ, CBR, PDF, and EPUB in the browser. OPDS support for apps like Tachiyomi; multi-user with reading progress and library-level permissions.

**Homepage:** https://komga.org  
**Docs:** https://komga.org/docs  
**GitHub:** https://github.com/gotson/komga  
**Docker:** https://hub.docker.com/r/gotson/komga  

Access via Caddy at **https://komga.yourdomain.com** (or your configured hostname).

## Quick start

1. Copy `stack.env.example` → `stack.env` (optional: set `TZ`, or `JAVA_TOOL_OPTIONS` for large libraries). For bind-mounted libraries, ensure the host directory is owned by the container user (gotson/komga runs as UID 1000), e.g. `chown -R 1000:1000 /path/to/comics`.
2. From the stack directory: `docker compose up -d`.
3. Open the web UI, create the first user (admin), then add libraries pointing at `/data` (default) or bind-mount your comic folders to `/data` (see **Library** below).

**Portainer:** Add stack → paste `docker-compose.yml` → set env vars from `stack.env` if needed → deploy.

## Library

By default the stack uses a named volume `komga_data` for `/data`. To use existing folders, replace the volume with a bind mount in `docker-compose.yml`, e.g.:

```yaml
volumes:
  - /path/to/your/comics:/data
```

Create libraries in the Komga UI; choose a directory under `/data` (e.g. `/data/comics`). Komga recommends a local filesystem for `/config` (no NFS/CIFS).

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `komga:25600`) |
| **Network** | `monitor` |
| **Images** | `gotson/komga:latest` |
| **Storage** | Named volumes: `komga_config` (DB and settings), `komga_data` (books); or bind-mount `/data` |

## Caddy reverse proxy

Add a site block for the Komga hostname (e.g. `komga.yourdomain.com`):

```
komga.yourdomain.com {
	reverse_proxy komga:25600
}
```

## Health and monitoring

Komga does not expose a dedicated health endpoint. Use a generic HTTP check to the app URL (e.g. `https://komga.yourdomain.com`) in Uptime Kuma.
