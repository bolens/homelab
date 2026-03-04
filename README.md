# 🐳 Docker homelab

A collection of **Docker Compose stacks** for self-hosting at home: reverse proxy, monitoring, auto-updates, document management, search, and optional Cloudflare Tunnels. Each stack lives in its own folder with a dedicated README—pick what you need and run it.

---

## 🗺️ Topology

```mermaid
flowchart TB
    subgraph internet["Internet / LAN"]
        users["Clients"]
    end

    subgraph ingress["Ingress"]
        tunnel["cloudflare-tunnel<br>(optional)"]
        caddy["caddy<br>Reverse proxy<br>:80 / :443"]
    end

    subgraph apps["Application stacks"]
        vaultwarden["vaultwarden"]
        immich["immich"]
        paperless["paperless-ngx"]
        mealie["mealie"]
        linkwarden["linkwarden"]
        archivebox["archivebox"]
        audiobookshelf["audiobookshelf"]
        freshrss["freshrss"]
        searx["searx-ng"]
        slink["slink"]
        socialhunt["social-hunt"]
        maigret["maigret"]
        webcheck["web-check"]
        ittools["it-tools"]
        convertx["convertx"]
        dozzle["dozzle"]
        infisical["infisical"]
        privatebin["privatebin"]
        pwpush["pwpush"]
        simplelogin["simplelogin"]
        onionprobe["onionprobe"]
        ail["ail"]
        naisho["naisho"]
        stoat["stoat"]
        shortener["yourls"]
        linkstack["linkstack"]
        ollama["ollama"]
        opennotebook["open-notebook"]
        perplexica["perplexica"]
        openwebui["open-webui"]
        librechat["librechat"]
        n8n["n8n"]
    end

    subgraph infra["Infrastructure"]
        portainer["portainer<br>Docker UI"]
        watchtower["watchtower<br>Auto-updates"]
        diun["diun<br>Image update notifier"]
        kuma["uptime-kuma<br>Monitoring"]
        headscale["headscale<br>Mesh VPN"]
        grafana["grafana<br>Dashboards"]
        prometheus["prometheus<br>Metrics"]
        cadvisor["cAdvisor<br>Container metrics"]
    end

    users --> tunnel
    users --> caddy
    tunnel --> caddy
    caddy --> vaultwarden & immich & paperless & mealie & linkwarden & archivebox & audiobookshelf & freshrss & searx & slink & socialhunt & maigret & webcheck & ittools & convertx & dozzle & n8n & infisical & privatebin & pwpush & simplelogin & onionprobe & ail & naisho & stoat & shortener & linkstack & ollama & opennotebook & perplexica & openwebui & librechat
    caddy --> grafana & prometheus & cadvisor
    kuma -.->|health checks| caddy
    prometheus -.->|scrapes| cadvisor
    grafana -.->|queries| prometheus
    watchtower -.->|updates| apps
    diun -.->|notifies| users
    portainer -.->|manages| apps
```

- **Traffic:** Clients hit Caddy (directly via local DNS or through Cloudflare Tunnel). Caddy routes by hostname to each app.
- **Infrastructure:** Portainer manages stacks; Watchtower updates images; Diun notifies when image tags change (e.g. Telegram/Discord); Uptime Kuma monitors Caddy and app health endpoints; Headscale provides Tailscale-compatible mesh VPN. Dozzle (behind Caddy) is a log viewer for all containers.

---

## 📦 What’s inside

| Stack | What it does |
|-------|----------------|
| **portainer** | Docker management UI (Portainer CE) |
| **stacks/ail** | AIL framework – analyse information leaks (pastes, trackers, MISP/TheHive, credentials/cards/keys detection) |
| **stacks/archivebox** | Self-hosted web archive (ArchiveBox) – saves full snapshots (HTML, screenshots, PDFs, WARCs) from URLs and feeds |
| **stacks/audiobookshelf** | Audiobook and podcast server |
| **stacks/caddy** | Reverse proxy with automatic HTTPS (Let’s Encrypt, optional Cloudflare DNS-01) |
| **stacks/cadvisor** | Container resource metrics (CPU, memory, etc.) |
| **stacks/cloudflare-tunnel** | Expose services via Cloudflare without port forwarding (cloudflared) |
| **stacks/convertx** | Self-hosted online file converter (1000+ formats: documents, images, video, e-books) |
| **stacks/dependency-track** | OWASP Dependency-Track – SBOM/dependency vulnerability tracking (upload CycloneDX/SPDX, CVE alerts) |
| **stacks/diun** | Docker image update notifier (Telegram, Discord, etc.) |
| **stacks/dozzle** | Real-time container log viewer |
| **stacks/freshrss** | RSS feed aggregator (Feedly-like) |
| **stacks/grafana** | Metrics dashboards (use with Prometheus + cAdvisor) |
| **stacks/headscale** | Self-hosted Tailscale control server (mesh VPN) |
| **stacks/immich** | Photo and video backup (OAuth-ready) |
| **stacks/infisical** | Self-hosted secrets manager (API keys, env vars, config) |
| **stacks/it-tools** | Developer and IT utilities (converters, hashes, QR, etc.) |
| **stacks/librechat** | ChatGPT-style UI with agents, MCP, code interpreter (MongoDB + Redis) |
| **stacks/linkstack** | Self-hosted link-in-bio page (Linktree-style: one URL with your links) |
| **stacks/linkwarden** | Bookmark manager and link aggregator |
| **stacks/maigret** | OSINT: collect a dossier by username from thousands of sites (web UI, HTML/PDF/XMind reports) |
| **stacks/mealie** | Recipe manager and meal planner |
| **stacks/n8n** | Workflow automation (Zapier/Make-style, self-hosted) |
| **stacks/naisho** | Send data deletion request emails to data brokers at once (Rails app; SMTP in UI) |
| **stacks/ollama** | Local LLM runtime (Ollama) with GPU support and configurable model storage |
| **stacks/onionprobe** | Tor Onion Services monitoring (probe endpoints, Prometheus + Grafana + Alertmanager) |
| **stacks/onionscan** | CLI to investigate Tor hidden services (OnionScan; scans for opsec/misconfig, runs over Tor in container) |
| **stacks/open-notebook** | Open-source Notebook LM alternative (SurrealDB + multi-provider AI) |
| **stacks/open-webui** | Self-hosted AI chat UI; Ollama model management and multi-provider support |
| **stacks/paperless-ngx** | Document management with OCR and search |
| **stacks/password-pusher** | Password/secret sharing with view limits and expiration (Password Pusher) |
| **stacks/perplexica** | Privacy-focused AI answering engine (bundled SearxNG, optional Ollama) |
| **stacks/privatebin** | Encrypted pastebin (share text with expiration, no account) |
| **stacks/prometheus** | Metrics collection and storage |
| **stacks/privotron** | CLI to automate data broker opt-outs (Playwright; profiles, skip list, parallel runs) |
| **stacks/searx-ng** | Privacy-respecting metasearch engine |
| **stacks/simplelogin** | Email alias service (unlimited aliases, forward & reply anonymously, Bitwarden/1Password) |
| **stacks/slink** | Self-hosted image sharing (upload, collections, ShareX, S3/SMB) |
| **stacks/social-hunt** | OSINT framework: username search, breach lookups (HIBP/Snusbase), face match, reverse image |
| **stacks/stoat** | Self-hosted Stoat chat platform (API, web, media, notifications, optional voice) |
| **stacks/threat-dragon** | OWASP Threat Dragon – threat modeling (diagrams, STRIDE; save to GitHub/Bitbucket/GitLab) |
| **stacks/torbot** | OWASP TorBot – Dark Web OSINT crawler (.onion crawl, email extraction, link tree, JSON export; Tor in separate container) |
| **stacks/uptime-kuma** | Status page and monitoring |
| **stacks/vaultwarden** | Lightweight Bitwarden-compatible password manager |
| **stacks/watchtower** | Automatic container image updates (nickfedor fork, Docker 29+) |
| **stacks/web-check** | OSINT and website analysis tool |
| **stacks/yourls** | Self-hosted URL shortener (YOURLS): short links, web UI, optional API |
| **stacks/zap** | OWASP ZAP – web/API security scanner (daemon + web UI; baseline/active scans; access via Caddy) |

Each stack has its own **README** with setup and usage; see also `portainer/README.md`.

### Optional: services that make maintenance easier

Beyond Portainer, Uptime Kuma, and Watchtower, these can reduce friction when running and debugging the stacks:

| Idea | What it does | Why it helps |
|------|----------------|--------------|
| **Dozzle** | Real-time container log viewer (single container, Docker socket) | When something breaks, see which container and what it logged without `docker logs` or Portainer log tabs. |
| **Backup** (e.g. **Restic** or **Duplicati**) | Backs up volumes and/or configs to local/NAS/S3/B2 | Configs are in git; app data (DBs, uploads) is not. A scheduled backup avoids losing data on bad updates or disk failure. |
| **Diun** | Notifies when new Docker image tags are available | Complements Watchtower: you see what images changed (e.g. Telegram/Discord/email) before or after Watchtower pulls. |
| **Grafana + Prometheus + cAdvisor** | Host and container metrics (CPU, memory, disk) | Uptime Kuma answers “is it up?”; these stacks answer “why is the host slow?” and help plan capacity. Deploy all three on the `monitor` network; see each stack’s README. |
| **Cloudflare Access (SSO)** | Login in front of tunnel subdomains | Use Zero Trust Access to protect e.g. `portainer.yourdomain.com` with Google/GitHub SSO or one-time PIN instead of basic auth. See [documents/ACCESS-SSO.md](documents/ACCESS-SSO.md). |
| **Scrutiny** | SMART disk health dashboard | Optional; useful if the host has physical disks—warn before failure. |

**Dozzle**, **Diun**, **Grafana**, **Prometheus**, and **cAdvisor** are included as stacks. Dozzle and the metrics stack are behind Caddy (see Caddyfile.example); Diun has no web UI.

---

## 🚀 Getting started

### 1. 🔐 Secrets and config

Sensitive files (`stack.env`, `config.yml`, `Caddyfile`, etc.) are gitignored. Copy from the `.example` templates in each stack and fill in your values:

- **stacks/ail** — optional `stack.env` with `TZ`; uses community image cciucd/ail-framework; >6GB RAM recommended; reset password after first login: `docker exec ail bin/LAUNCH.sh -rp`
- **stacks/archivebox** — `stack.env.example` → `stack.env`; set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SEARCH_BACKEND_PASSWORD` (and adjust `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` for your Caddy hostnames)
- **stacks/caddy** — `stack.env.example` → `stack.env` (for Cloudflare DNS), `Caddyfile.example` → `Caddyfile`
- **stacks/cadvisor** — no config files
- **stacks/cloudflare-tunnel** — `stack.env.example` → `stack.env`, optionally `config.yml.example` → `config.yml`. To put tunnel subdomains behind SSO (e.g. Google/GitHub) instead of basic auth, see [documents/ACCESS-SSO.md](documents/ACCESS-SSO.md).
- **stacks/convertx** — `stack.env.example` → `stack.env`; set `JWT_SECRET` (recommended; `openssl rand -base64 32`); set `ACCOUNT_REGISTRATION=false` after first account
- **stacks/dependency-track** — `stack.env.example` → `stack.env`; set `POSTGRES_PASSWORD` and `API_BASE_URL` (URL the browser uses for the API, e.g. https://dtrack.home/api). See stack README for Caddy path/subdomain setup.
- **stacks/diun** — `stack.env.example` → `stack.env`; set `DIUN_NOTIF_TELEGRAM_TOKEN` and `DIUN_NOTIF_TELEGRAM_CHATIDS` (or another notifier)
- **stacks/dozzle** — no secrets; optional `DOZZLE_AUTH_*` for simple auth (see stack README)
- **stacks/freshrss** — `stack.env.example` → `stack.env`; optional `PUID`, `PGID`, `TZ`
- **stacks/grafana** — optional `stack.env` for `GF_SERVER_ROOT_URL` (e.g. https://grafana.yourdomain.com)
- **stacks/headscale** — `stack.env.example` → `stack.env`; create `config.yaml` from `config.example.yaml`, then set `HEADSCALE_CONFIG_B64` to its base64 (e.g. `base64 -w 0 config.yaml`) in `stack.env` or in Portainer stack env
- **stacks/immich** — `stack.env.example` → `stack.env`; set `DB_PASSWORD` (and optionally `TZ`, OAuth via Admin UI)
- **stacks/infisical** — `stack.env.example` → `stack.env`; set `ENCRYPTION_KEY`, `AUTH_SECRET`, `POSTGRES_PASSWORD`, `SITE_URL` (e.g. `https://infisical.home` or `https://secrets.yourdomain.com`)
- **stacks/librechat** — `stack.env.example` → `stack.env`; set `JWT_SECRET`, `JWT_REFRESH_SECRET` (e.g. `openssl rand -base64 32`); set `MONGO_INITDB_ROOT_PASSWORD`, `REDIS_PASSWORD`; set `OLLAMA_BASE_URL` if using Ollama
- **stacks/linkstack** — `stack.env.example` → `stack.env` (all vars optional); optional `HTTP_SERVER_NAME` / `HTTPS_SERVER_NAME` when behind Caddy
- **stacks/linkwarden** — `stack.env.example` → `stack.env`; set `NEXTAUTH_SECRET`, `POSTGRES_PASSWORD`, `MEILI_MASTER_KEY` (and `NEXTAUTH_URL` if behind Caddy)
- **stacks/maigret** — no required env; optional TZ. Deploy and access via Caddy (e.g. https://maigret.home)
- **stacks/mealie** — `stack.env.example` → `stack.env`; set `BASE_URL` if behind Caddy, `ALLOW_SIGNUP` (false after first account)
- **stacks/n8n** — `stack.env.example` → `stack.env`; set `N8N_HOST` and `WEBHOOK_URL` to your Caddy URL (e.g. https://n8n.home or https://n8n.yourdomain.com); optional `N8N_ENCRYPTION_KEY`
- **stacks/naisho** — `stack.env.example` → `stack.env`; set `SECRET_KEY_BASE` (`openssl rand -hex 64`); stack builds from GitHub on first deploy; configure SMTP in the app when sending deletion emails
- **stacks/ollama** — `stack.env.example` → `stack.env`; optional `OLLAMA_MODELS_PATH` (absolute path recommended for models); other data uses Docker volume; GPU requires NVIDIA Container Toolkit
- **stacks/onionprobe** — run `./clone-repo.sh` once to clone the upstream repo into `./repo`; optional `stack.env` for `GRAFANA_DATABASE_PASSWORD`, `GF_SERVER_ROOT_URL`; access via Caddy (onionprobe.home → Grafana)
- **stacks/onionscan** — CLI only; no web UI or ports. Optional: `stack.env` with TZ. Start with `docker compose up -d`, wait for Tor (logs), then `docker compose exec onionscan onionscan [options] <onion-address>`. See stack README.
- **stacks/open-notebook** — `stack.env.example` → `stack.env`; set `OPEN_NOTEBOOK_ENCRYPTION_KEY` (e.g. `openssl rand -base64 32`); optional `OLLAMA_BASE_URL`
- **stacks/open-webui** — `stack.env.example` → `stack.env`; set `OLLAMA_BASE_URL` to reach Ollama (e.g. `http://ollama:11434` or `http://host.docker.internal:11434`)
- **stacks/paperless-ngx** — `stack.env.example` → `stack.env`; set `PAPERLESS_URL`, `PAPERLESS_SECRET_KEY`
- **stacks/password-pusher** — `stack.env.example` → `stack.env`; set `PWPUSH_MASTER_KEY` (generate at https://us.pwpush.com/generate_key); optional `PWP__HOST_DOMAIN` if behind Caddy
- **stacks/perplexica** — `stack.env.example` → `stack.env`; optional `PERPLEXICA_DATA_PATH`, `SEARXNG_API_URL`, `OLLAMA_BASE_URL`
- **stacks/privotron** — no `stack.env` required; `docker compose build` then `docker compose run --rm privotron --profile NAME` (create profile with `--save-profile`). Optional: `PRIVOTRON_VERSION` when building; mount `./brokers` for `.skipbrokers`. See stack README.
- **stacks/prometheus** — no secrets; `prometheus.yml` is in the repo
- **stacks/searx-ng** — `stack.env.example` → `stack.env`; set `SEARXNG_SECRET` (and optionally `SEARXNG_BASE_URL`)
- **stacks/simplelogin** — `stack.env.example` → `stack.env`; create `data/dkim.key` (see README); set `URL`, `EMAIL_DOMAIN`, `EMAIL_SERVERS_WITH_PRIORITY`, `SUPPORT_EMAIL`, `FLASK_SECRET` (`openssl rand -hex 32`), `POSTGRES_PASSWORD`; run migration and init once (see stack README)
- **stacks/slink** — `stack.env.example` → `stack.env`; set `ORIGIN` to your Caddy URL (e.g. https://slink.home or https://slink.yourdomain.com)
- **stacks/stoat** — no `stack.env.example`; from the stack directory, download and run `generate_config.sh` from `stoatchat/self-hosted` to create `.env.web`, `Revolt.toml`, and `livekit.yml`; then optionally change `HOSTNAME=:80` in `.env.web` when running behind this repo’s main Caddy; see stack README and upstream docs for advanced config
- **stacks/threat-dragon** — `stack.env.example` → `stack.env`; set `SESSION_SIGNING_KEY` (e.g. `openssl rand -hex 16`); for repo storage set GitHub/Bitbucket/GitLab OAuth vars. See stack README.
- **stacks/torbot** — CLI only (OWASP TorBot). No ports. Optional: `stack.env` with TZ. Start with `docker compose up -d`, wait for Tor (`docker compose logs -f tor`), then `docker compose exec torbot torbot -u <url> --host tor --port 9050 [options]`. See stack README.
- **stacks/vaultwarden** — `stack.env.example` → `stack.env`; set `DOMAIN` if behind Caddy, `SIGNUPS_ALLOWED` (false after first account)
- **stacks/web-check** — optional: `stack.env.example` → `stack.env` for API keys
- **stacks/watchtower** — TZ, LANG, LC_ALL, LC_CTYPE in `stack.env` if you choose to override defaults
- **stacks/yourls** — `stack.env.example` → `stack.env`; set `YOURLS_SITE` (e.g. https://short.home or https://short.yourdomain.com) to match Caddy hostname; set `YOURLS_USER`, `YOURLS_PASS`, `YOURLS_COOKIEKEY`, `YOURLS_DB_PASSWORD`, `YOURLS_DB_ROOT_PASSWORD`
- **stacks/zap** — Optional: `stack.env` with TZ. No host ports; access via Caddy (e.g. https://zap.home). See stack README.

### 2. ⚙️ Shared settings

For timezone, locale, and optional per-app settings, see **[documents/ENV-VARS.md](documents/ENV-VARS.md)**.

### 3. ▶️ Deploy

From a stack directory: `docker compose --env-file stack.env up -d`, or add the stack in Portainer (Git deploy so bind-mounted config files are present).

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
| **password-pusher** | `/up` |
| **yourls** | (no dedicated health endpoint; use HTTP check to app URL) |
| **ollama** | (API only; use HTTP check to `http://ollama:11434` or `/api/tags`) |
| **open-notebook** | (use HTTP check to app URL) |
| **perplexica** | (use HTTP check to app URL) |
| **open-webui** | (use HTTP check to app URL) |
| **librechat** | (use HTTP check to app URL) |
| **convertx** | (use HTTP check to app URL) |
| **slink** | (use HTTP check to app URL) |
| **n8n** | `/healthz` |

Other stacks (paperless-ngx, linkwarden, searx-ng, linkstack, caddy, infisical, etc.) have no dedicated health endpoint; use an HTTP check to the app URL if needed.

---

## 📁 Layout

```
docker/
├── portainer/          # Portainer stack
├── stacks/
│   ├── caddy/          # Reverse proxy
│   ├── cloudflare-tunnel/
│   ├── diun/
│   ├── dozzle/
│   ├── n8n/
│   ├── uptime-kuma/
│   ├── grafana/
│   ├── prometheus/
│   ├── cadvisor/
│   ├── watchtower/
│   ├── audiobookshelf/
│   ├── freshrss/
│   ├── it-tools/
│   ├── convertx/
│   ├── archivebox/
│   ├── immich/
│   ├── infisical/
│   ├── mealie/
│   ├── paperless-ngx/
│   ├── searx-ng/
│   ├── slink/
│   ├── web-check/
│   ├── vaultwarden/
│   ├── headscale/
│   ├── linkwarden/
│   ├── password-pusher/
│   ├── privatebin/
│   ├── yourls/
│   ├── linkstack/
│   ├── ollama/
│   ├── open-notebook/
│   ├── perplexica/
│   ├── open-webui/
│   └── librechat/
├── documents/          # ENV-VARS.md, ACCESS-SSO.md, other guides
└── .gitignore          # Excludes .env, config.yml, Caddyfile, etc.
```
