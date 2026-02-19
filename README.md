# Docker stacks

Docker Compose stacks for self-hosting: reverse proxy, monitoring, auto-updates, document management, search, and optional Cloudflare Tunnels.

## Stacks

| Stack | Description |
|-------|-------------|
| **portainer** | Portainer CE – Docker management UI |
| **stacks/caddy** | Caddy reverse proxy with automatic HTTPS (Let’s Encrypt, optional Cloudflare DNS-01) |
| **stacks/cloudflare-tunnel** | Cloudflared – expose services via Cloudflare without port forwarding |
| **stacks/uptime-kuma** | Uptime Kuma – status page and monitoring |
| **stacks/watchtower** | Watchtower – automatic container image updates (nickfedor fork, Docker 29+) |
| **stacks/it-tools** | IT Tools – developer and IT utilities (converters, hashes, QR, etc.) |
| **stacks/paperless-ngx** | Paperless-ngx – document management with OCR and search |
| **stacks/searx-ng** | SearXNG – privacy-respecting metasearch engine |
| **stacks/web-check** | Web-Check – OSINT and website analysis tool |

Each stack has its own `README.md` with setup and usage; see also `portainer/README.md`.

## Getting started

1. **Secrets and config** – Files like `.env`, `config.yml`, and `Caddyfile` are gitignored. Copy from the `.example` templates and fill in your values:
   - `stacks/caddy`: copy `.env.example` → `.env` (for Cloudflare DNS), `Caddyfile.example` → `Caddyfile`
   - `stacks/cloudflare-tunnel`: copy `.env.example` → `.env`, optionally `config.yml.example` → `config.yml`
   - `stacks/paperless-ngx`: copy `.env.example` → `.env` and set `PAPERLESS_URL`, `PAPERLESS_SECRET_KEY`
   - `stacks/searx-ng`: copy `.env.example` → `.env` and set `SEARXNG_SECRET` (and optionally `SEARXNG_BASE_URL`)
   - `stacks/web-check`: optional – copy `.env.example` → `.env` for API keys if desired
2. **Common env vars** – See [stacks/ENV-VARS.md](stacks/ENV-VARS.md) for timezone, locale, and optional per-app settings.
3. **Deploy** – From a stack directory: `docker compose up -d`, or add the stack in Portainer (Git deploy so bind-mounted config files are present).

## Layout

```
docker/
├── portainer/          # Portainer stack
├── stacks/
│   ├── caddy/          # Reverse proxy
│   ├── cloudflare-tunnel/
│   ├── uptime-kuma/
│   ├── watchtower/
│   ├── it-tools/
│   ├── paperless-ngx/
│   ├── searx-ng/
│   ├── web-check/
│   └── ENV-VARS.md     # Shared env var reference
└── .gitignore          # Excludes .env, config.yml, Caddyfile, etc.
```
