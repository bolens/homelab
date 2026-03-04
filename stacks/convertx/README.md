# ConvertX

Self-hosted online file converter supporting **1000+ formats**: documents (LibreOffice, Pandoc), images (ImageMagick, Vips, HEIF, JPEG XL), video (FFmpeg), e-books (Calibre), 3D (Assimp), and more. Written with TypeScript, Bun and Elysia.

**GitHub:** https://github.com/C4illin/ConvertX

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `JWT_SECRET` (recommended). Generate with `openssl rand -base64 32`; if unset, the app uses a random UUID (sessions may reset on restart).
2. **Deploy:** `docker compose --env-file stack.env up -d` (or add the stack in Portainer and set the same vars in the stack Environment).
3. **Access:** Open via Caddy (e.g. https://convertx.home or https://convertx.yourdomain.com). Create your account on first visit; then set `ACCOUNT_REGISTRATION=false` in `stack.env` to prevent others from registering.

The stack uses a **named volume** for app data (SQLite, converted files), so it works when deployed from Portainer.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `convertx:3000`) |
| **Network** | `monitor` (external) — Caddy can reverse-proxy to `convertx:3000` |
| **Image** | `ghcr.io/c4illin/convertx:latest` |
| **Env** | `JWT_SECRET` (recommended); optional `TZ`, `ACCOUNT_REGISTRATION`, `HTTP_ALLOWED`, `LANGUAGE`, `AUTO_DELETE_EVERY_N_HOURS`, etc. |
| **Storage** | Named volume `convertx-data` (database + converted files) |

## Features

- Convert files to many formats (documents, images, video, e-books, 3D, data files).
- Process multiple files at once.
- Password-protected conversions.
- Multiple accounts (disable registration after creating yours).

If you use the service over HTTP (not HTTPS), set `HTTP_ALLOWED=true` or login may fail; behind Caddy with HTTPS leave it `false`.

## Caddy reverse proxy

Example Caddy vhost (e.g. in your Caddyfile):

```
convertx.home, convertx.yourdomain.com {
  reverse_proxy convertx:3000
}
```

Ensure the stack is on the `monitor` network so Caddy can reach `convertx:3000`.

## Start

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose and set `JWT_SECRET` (and optional vars) in **Environment**.
