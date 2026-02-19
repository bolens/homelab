# Docker stacks

Docker Compose stacks for self-hosting: reverse proxy, monitoring, auto-updates, document management, search, and optional Cloudflare Tunnels.

## Stacks

| Stack | Description |
|-------|-------------|
| **portainer** | Portainer CE – Docker management UI |
| **stacks/caddy** | Caddy reverse proxy with automatic HTTPS (Let’s Encrypt, optional Cloudflare DNS-01) |
| **stacks/cloudflare-tunnel** | Cloudflared – expose services via Cloudflare without port forwarding |
| **stacks/headscale** | Headscale – self-hosted Tailscale control server (mesh VPN) |
| **stacks/audiobookshelf** | Audiobookshelf – self-hosted audiobook and podcast server |
| **stacks/freshrss** | FreshRSS – self-hosted RSS feed aggregator (Feedly-like) |
| **stacks/immich** | Immich – self-hosted photo and video backup (OAuth-ready) |
| **stacks/it-tools** | IT Tools – developer and IT utilities (converters, hashes, QR, etc.) |
| **stacks/linkwarden** | Linkwarden – self-hosted bookmark manager and link aggregator |
| **stacks/mealie** | Mealie – self-hosted recipe manager and meal planner |
| **stacks/paperless-ngx** | Paperless-ngx – document management with OCR and search |
| **stacks/searx-ng** | SearXNG – privacy-respecting metasearch engine |
| **stacks/uptime-kuma** | Uptime Kuma – status page and monitoring |
| **stacks/vaultwarden** | Vaultwarden – lightweight Bitwarden-compatible password manager |
| **stacks/watchtower** | Watchtower – automatic container image updates (nickfedor fork, Docker 29+) |
| **stacks/web-check** | Web-Check – OSINT and website analysis tool |

Each stack has its own `README.md` with setup and usage; see also `portainer/README.md`.

### Health endpoints (Uptime Kuma)

These stacks expose a dedicated health/status URL so you can monitor them without just hitting the main page:

| Stack        | Endpoint                    |
|-------------|-----------------------------|
| **headscale**      | `/health`                   |
| **vaultwarden**    | `/alive`                    |
| **immich**         | `/api/server/ping`          |
| **audiobookshelf** | `/healthcheck`              |
| **mealie**         | `/api/app/about`            |

Other stacks (paperless-ngx, linkwarden, searx-ng, caddy, etc.) have no dedicated health endpoint; use an HTTP check to the app URL if needed.

## Getting started

1. **Secrets and config** – Files like `.env`, `config.yml`, and `Caddyfile` are gitignored. Copy from the `.example` templates and fill in your values:
   - `stacks/caddy`: copy `.env.example` → `.env` (for Cloudflare DNS), `Caddyfile.example` → `Caddyfile`
   - `stacks/cloudflare-tunnel`: copy `.env.example` → `.env`, optionally `config.yml.example` → `config.yml`
   - `stacks/paperless-ngx`: copy `.env.example` → `.env` and set `PAPERLESS_URL`, `PAPERLESS_SECRET_KEY`
   - `stacks/immich`: copy `.env.example` → `.env` and set `DB_PASSWORD` (and optionally `TZ`, OAuth via Admin UI)
   - `stacks/searx-ng`: copy `.env.example` → `.env` and set `SEARXNG_SECRET` (and optionally `SEARXNG_BASE_URL`)
   - `stacks/web-check`: optional – copy `.env.example` → `.env` for API keys if desired
   - `stacks/vaultwarden`: copy `.env.example` → `.env`; set `DOMAIN` if behind Caddy, `SIGNUPS_ALLOWED` (false after first account)
   - `stacks/headscale`: copy `.env.example` → `.env`; create `config.yaml` from `config.example.yaml`, then set `HEADSCALE_CONFIG_B64` to its base64 (e.g. `base64 -w 0 config.yaml`) in `.env` or in Portainer stack env
   - `stacks/linkwarden`: copy `.env.example` → `.env` and set `NEXTAUTH_SECRET`, `POSTGRES_PASSWORD`, `MEILI_MASTER_KEY` (and `NEXTAUTH_URL` if behind Caddy)
   - `stacks/mealie`: copy `.env.example` → `.env`; set `BASE_URL` if behind Caddy, `ALLOW_SIGNUP` (false after first account)
   - `stacks/freshrss`: copy `.env.example` → `.env`; optional `PUID`, `PGID`, `TZ`
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
│   ├── audiobookshelf/
│   ├── freshrss/
│   ├── it-tools/
│   ├── immich/
│   ├── mealie/
│   ├── paperless-ngx/
│   ├── searx-ng/
│   ├── web-check/
│   ├── vaultwarden/
│   ├── headscale/
│   ├── linkwarden/
│   └── ENV-VARS.md     # Shared env var reference
└── .gitignore          # Excludes .env, config.yml, Caddyfile, etc.
```
