# LinkStack

Self-hosted **link-in-bio** page (Linktree-style): one URL that shows your profile and a list of links (social, projects, etc.). Customizable themes, optional multi-user, no database required—data lives in the container volume.

**Website:** https://linkstack.org  
**Docs:** https://docs.linkstack.org  
**GitHub:** https://github.com/linkstackorg/linkstack

## Quick start

1. **Environment**
   - Copy `.env.example` to `.env` (all vars optional; defaults are fine for local use).
   - Optionally set `HTTP_SERVER_NAME` and `HTTPS_SERVER_NAME` to your Caddy hostname (e.g. `linkstack.home`) if the app needs to know its URL.
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer and set env in the stack Environment).
3. **Access:** Open via Caddy (e.g. https://linkstack.home or https://linkstack.yourdomain.com). First visit: create your profile and add links.

The stack uses a **named volume** for app data (`/htdocs`), so it works when deployed from Portainer.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `linkstack:80`) |
| **Network** | `monitor` (external) — Caddy can reverse-proxy to `linkstack:80` |
| **Image** | `linkstackorg/linkstack:latest` |
| **Env** | All optional: `TZ`, `SERVER_ADMIN`, `HTTP_SERVER_NAME`, `HTTPS_SERVER_NAME`, `LOG_LEVEL`, `PHP_MEMORY_LIMIT`, `UPLOAD_MAX_FILESIZE` |
| **Storage** | Named volume `linkstack-data` (profiles, links, themes, uploads) |

## Features

- **Single-page links** — One URL with your bio and clickable links.
- **Themes** — Built-in and community themes; customizable CSS.
- **Optional multi-user** — Multiple profiles on one instance.
- **No database** — File-based; data in the volume.
- **Export/import** — Move data between instances.

## Caddy reverse proxy

When LinkStack is behind Caddy (HTTPS in front, HTTP to the container), the app may generate `http://` URLs and trigger mixed-content errors. The Caddy blocks below send **X-Forwarded-Proto** and **X-Forwarded-Host** and add **Content-Security-Policy: upgrade-insecure-requests** so the browser upgrades any insecure requests to HTTPS.

Example Caddy vhost (e.g. in your Caddyfile):

```
linkstack.home, linkstack.local {
  tls internal
  header Content-Security-Policy "upgrade-insecure-requests"
  reverse_proxy linkstack:80 {
    header_up X-Forwarded-Proto https
    header_up X-Forwarded-Host {host}
  }
}

linkstack.yourdomain.com {
  tls {
    dns cloudflare {env.CLOUDFLARE_API_TOKEN}
  }
  header Content-Security-Policy "upgrade-insecure-requests"
  reverse_proxy linkstack:80 {
    header_up X-Forwarded-Proto https
    header_up X-Forwarded-Host {host}
  }
}
```

Ensure the stack is on the `monitor` network so Caddy can reach `linkstack:80`.

## Start

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose and set any optional env vars in **Environment**.
