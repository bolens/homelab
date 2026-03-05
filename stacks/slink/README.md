# Slink

Self-hosted **image sharing** platform: upload images (PNG, JPG, WEBP, SVG, AVIF, HEIC, etc.), create collections, share links, ShareX integration, optional guest uploads. Built with Symfony and SvelteKit.

**Website:** https://slinkapp.io  
**Docs:** https://docs.slinkapp.io  
**GitHub:** https://github.com/andrii-kryvoviaz/slink  
**Docker image:** https://hub.docker.com/r/anirdev/slink  
**Releases:** https://github.com/andrii-kryvoviaz/slink/releases  

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `ORIGIN` to your public URL (e.g. `https://slink.home` or `https://slink.yourdomain.com`). Must match the Caddy hostname for cookies and redirects.
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer and set the same vars in the stack Environment).
3. **Access:** Open via Caddy (e.g. https://slink.home or https://slink.yourdomain.com). Create your first admin user (or set `ADMIN_*` once and remove after setup).

The stack uses **named volumes** for database and images (`slink-var-data`, `slink-images`), so it works when deployed from Portainer.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `slink:3000`) |
| **Network** | `monitor` (external) — Caddy can reverse-proxy to `slink:3000` |
| **Image** | `anirdev/slink:latest` |
| **Env** | `ORIGIN` (required); optional `TZ`, `USER_APPROVAL_REQUIRED`, `IMAGE_MAX_SIZE`, `STORAGE_PROVIDER`, etc. |
| **Storage** | Named volumes `slink-var-data` (DB), `slink-images` (uploads). For SMB or S3, set `STORAGE_PROVIDER` and see [Slink docs](https://docs.slinkapp.io). If you bind-mount a host path for images or data, ensure it is owned by the container user (e.g. `chown -R 1000:1000 /path`) so the app can write and you can read files as your host user. |

## Features

- Multi-format uploads, compression, EXIF stripping.
- Collections, tags, comments, bookmarks, ShareX integration.
- User approval flow, guest uploads, API keys, public API.
- Storage: local, SMB, or AWS S3–compatible.

## Caddy reverse proxy

Example Caddy vhost (e.g. in your Caddyfile):

```
slink.home, slink.yourdomain.com {
  reverse_proxy slink:3000
}
```

Ensure the stack is on the `monitor` network so Caddy can reach `slink:3000`.

## Start

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose and set `ORIGIN` (and optional vars) in **Environment**.
