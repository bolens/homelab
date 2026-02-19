# 🐳 Docker homelab

A collection of **Docker Compose stacks** for self-hosting at home: reverse proxy, monitoring, auto-updates, document management, search, and optional Cloudflare Tunnels. Each stack lives in its own folder with a dedicated README—pick what you need and run it.

---

## 📦 What’s inside

| Stack | What it does |
|-------|----------------|
| **portainer** | Docker management UI (Portainer CE) |
| **stacks/caddy** | Reverse proxy with automatic HTTPS (Let’s Encrypt, optional Cloudflare DNS-01) |
| **stacks/cloudflare-tunnel** | Expose services via Cloudflare without port forwarding (cloudflared) |
| **stacks/headscale** | Self-hosted Tailscale control server (mesh VPN) |
| **stacks/audiobookshelf** | Audiobook and podcast server |
| **stacks/freshrss** | RSS feed aggregator (Feedly-like) |
| **stacks/immich** | Photo and video backup (OAuth-ready) |
| **stacks/it-tools** | Developer and IT utilities (converters, hashes, QR, etc.) |
| **stacks/linkwarden** | Bookmark manager and link aggregator |
| **stacks/mealie** | Recipe manager and meal planner |
| **stacks/paperless-ngx** | Document management with OCR and search |
| **stacks/searx-ng** | Privacy-respecting metasearch engine |
| **stacks/uptime-kuma** | Status page and monitoring |
| **stacks/vaultwarden** | Lightweight Bitwarden-compatible password manager |
| **stacks/watchtower** | Automatic container image updates (nickfedor fork, Docker 29+) |
| **stacks/web-check** | OSINT and website analysis tool |

Each stack has its own **README** with setup and usage; see also `portainer/README.md`.

---

## 🚀 Getting started

### 1. 🔐 Secrets and config

Sensitive files (`.env`, `config.yml`, `Caddyfile`, etc.) are gitignored. Copy from the `.example` templates in each stack and fill in your values:

- **stacks/caddy** — `.env.example` → `.env` (for Cloudflare DNS), `Caddyfile.example` → `Caddyfile`
- **stacks/cloudflare-tunnel** — `.env.example` → `.env`, optionally `config.yml.example` → `config.yml`
- **stacks/paperless-ngx** — `.env.example` → `.env`; set `PAPERLESS_URL`, `PAPERLESS_SECRET_KEY`
- **stacks/immich** — `.env.example` → `.env`; set `DB_PASSWORD` (and optionally `TZ`, OAuth via Admin UI)
- **stacks/searx-ng** — `.env.example` → `.env`; set `SEARXNG_SECRET` (and optionally `SEARXNG_BASE_URL`)
- **stacks/web-check** — optional: `.env.example` → `.env` for API keys
- **stacks/vaultwarden** — `.env.example` → `.env`; set `DOMAIN` if behind Caddy, `SIGNUPS_ALLOWED` (false after first account)
- **stacks/headscale** — `.env.example` → `.env`; create `config.yaml` from `config.example.yaml`, then set `HEADSCALE_CONFIG_B64` to its base64 (e.g. `base64 -w 0 config.yaml`) in `.env` or in Portainer stack env
- **stacks/linkwarden** — `.env.example` → `.env`; set `NEXTAUTH_SECRET`, `POSTGRES_PASSWORD`, `MEILI_MASTER_KEY` (and `NEXTAUTH_URL` if behind Caddy)
- **stacks/mealie** — `.env.example` → `.env`; set `BASE_URL` if behind Caddy, `ALLOW_SIGNUP` (false after first account)
- **stacks/freshrss** — `.env.example` → `.env`; optional `PUID`, `PGID`, `TZ`

### 2. ⚙️ Shared settings

For timezone, locale, and optional per-app settings, see **[stacks/ENV-VARS.md](stacks/ENV-VARS.md)**.

### 3. ▶️ Deploy

From a stack directory: `docker compose up -d`, or add the stack in Portainer (Git deploy so bind-mounted config files are present).

---

## 💚 Health endpoints (Uptime Kuma)

These stacks expose a dedicated health/status URL so you can monitor them without hitting the main page:

| Stack | Endpoint |
|-------|----------|
| **headscale** | `/health` |
| **vaultwarden** | `/alive` |
| **immich** | `/api/server/ping` |
| **audiobookshelf** | `/healthcheck` |
| **mealie** | `/api/app/about` |

Other stacks (paperless-ngx, linkwarden, searx-ng, caddy, etc.) have no dedicated health endpoint; use an HTTP check to the app URL if needed.

---

## 📁 Layout

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
