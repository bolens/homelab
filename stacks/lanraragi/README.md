# Lanraragi

Tag-based comic and manga archive manager. Upload or drop CBR, CBZ, PDF, and other archives; organize with namespaced tags and plugins for metadata. Good for large, tag-heavy libraries (e.g. doujinshi, manga). Reads from archives without extracting.

**Homepage:** https://github.com/Difegue/LANraragi  
**Docs:** https://sugoi.gitbook.io/lanraragi  
**Docker:** https://hub.docker.com/r/difegue/lanraragi  

Access via Caddy at **https://lanraragi.yourdomain.com** (or your configured hostname).

## Quick start

1. Copy `stack.env.example` → `stack.env` (optional: set `TZ`, `LRR_UID`, `LRR_GID`).
2. From the stack directory: `docker compose up -d`.
3. Open the web UI; upload archives or place files in the content volume. Use the tag system and plugins (Settings → Plugins) to fetch metadata.

**Portainer:** Add stack → paste `docker-compose.yml` → set env vars → deploy.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `lanraragi:3000`) |
| **Network** | `monitor` |
| **Images** | `difegue/lanraragi:latest` |
| **Storage** | Named volumes: `lanraragi_content`, `lanraragi_database`, `lanraragi_thumb`; or bind-mount content |

## Caddy reverse proxy

Add a site block for the Lanraragi hostname (e.g. `lanraragi.yourdomain.com`):

```
lanraragi.yourdomain.com {
	reverse_proxy lanraragi:3000
}
```

## Health and monitoring

Lanraragi does not expose a dedicated health endpoint. Use a generic HTTP check to the app URL (e.g. `https://lanraragi.yourdomain.com`) in Uptime Kuma.
