# PrivateBin

Encrypted pastebin: share text snippets with optional expiration and password. No account required; pastes are encrypted in the browser before upload.

**Website:** https://privatebin.info  
**GitHub:** https://github.com/PrivateBin/PrivateBin

## Quick start

1. Deploy: `docker compose up -d`
2. Access via Caddy (e.g. https://paste.yourdomain.com or https://privatebin.home). No host port is exposed; the stack is on the `monitor` network for reverse-proxy.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `privatebin:8080`) |
| **Network** | `monitor` — so Caddy can reach it |
| **Image** | `privatebin/nginx-fpm-alpine:latest` |
| **Data** | Volume `privatebin_data` at `/srv/data` (paste storage) |

## Features

- **Client-side encryption** — pastes are encrypted in the browser; the server never sees plain text
- **Expiration** — burn after reading, 1 hour, 1 day, 1 week, 1 month, never
- **Optional password** — extra passphrase for decryption
- **Syntax highlighting** — for code snippets
- **No account** — create and share links immediately

## Start

From this directory: `docker compose up -d`.
