# 🐳 Docker homelab

A collection of **Docker Compose stacks** for self-hosting at home: reverse proxy, monitoring, auto-updates, document management, search, and optional Cloudflare Tunnels. Each stack lives in its own folder with a dedicated README—pick what you need and run it.

---

## 🗺️ Topology

The topology is generated from `documents/topology.yaml`. To regenerate it:

```bash
python3 scripts/build-topology.py --in-place
```

See [the generated topology](documents/TOPOLOGY.md) for ingress, VPN, application categories, monitoring, and service relationships.



---

## 📦 What’s inside

The catalog is generated from every `stacks/<name>/README.md`. Regenerate it
after adding or renaming a stack:

```bash
python3 scripts/build-stack-catalog.py
```

Browse the [generated stack catalog](documents/STACK-CATALOG.md) for every available stack and its purpose.

Each stack has its own **README** with setup and usage; see also `portainer/README.md`.

### Maintenance-related stacks and services

Beyond core infra like Portainer, Uptime Kuma, Watchtower, Prometheus, and Grafana, these stacks and services can further reduce friction when running and debugging the others:

| Idea | What it does | Why it helps |
|------|----------------|--------------|
| **Backups (Restic stack)** | Backs up volumes and/or configs to local/NAS/S3/B2 using restic | Configs are in git; app data (DBs, uploads) is not. The `stacks/restic` stack gives you a scheduled backup job so you avoid losing data on bad updates or disk failure. |
| **Cloudflare Access (SSO)** | Login in front of tunnel subdomains | Use Zero Trust Access to protect e.g. `portainer.yourdomain.com` with Google/GitHub SSO or one-time PIN instead of basic auth. See [documents/ACCESS-SSO.md](documents/ACCESS-SSO.md). |
| **Diun** | Notifies when new Docker image tags are available | Complements Watchtower: you see what images changed (e.g. Telegram/Discord/email) before or after Watchtower pulls. |
| **Dozzle** | Real-time container log viewer (single container, Docker socket) | When something breaks, see which container and what it logged without `docker logs` or Portainer log tabs. |
| **Grafana + Prometheus + cAdvisor** | Host and container metrics (CPU, memory, disk) | Uptime Kuma answers “is it up?”; these stacks answer “why is the host slow?” and help plan capacity. Deploy all three on the `monitor` network; see each stack’s README. |
| **Loki + Promtail** | Log aggregation and shipping | Query logs in Grafana (**Explore** → **Loki**). Deploy `stacks/loki` then `stacks/promtail` on `monitor`; Grafana datasources include Loki when using the example. |
| **Alertmanager + ntfy** | Alert routing and push notifications | Prometheus example config points at Alertmanager; Alertmanager example sends to ntfy. Deploy `stacks/alertmanager` and `stacks/ntfy` on `monitor`; subscribe to your topic in the ntfy app. |
| **Scrutiny** | SMART disk health dashboard | Optional; useful if the host has physical disks—warn before failure. |

All of these (except Cloudflare Access, which is configured via your Cloudflare account) are available as dedicated stacks in this repo; see the [stack catalog](documents/STACK-CATALOG.md) for links.

---

## 🚀 Getting started

For a new host or first deployment, follow the concise
**[Getting started guide](documents/GETTING-STARTED.md)** first. It covers
prerequisites, read-only checks, mounts, secrets, networks, deployment, and
verification. The catalog below is the per-stack reference.

### 1. 🔐 Secrets and config

Sensitive files (`stack.env`, `config.yml`, `Caddyfile`, etc.) are gitignored. Copy from the `.example` templates in each stack and fill in your values.

**Optional – shared TZ/locale:** From the `docker/` repo root, copy `shared.env.example` → `shared.env` and set your timezone and locale once; supported Compose files load it automatically. Add the same values in Portainer when deploying through its editor. See [documents/SHARED-RESOURCES.md](documents/SHARED-RESOURCES.md#1-shared-env-file-tz--locale).

- **stacks/ail** — optional `stack.env` with `TZ`; uses community image cciucd/ail-framework; >6GB RAM recommended; reset password after first login: `docker exec ail bin/LAUNCH.sh -rp`
- **stacks/anything-llm** — `./prepare-stack.sh`; set `JWT_SECRET` in `stack.env`; pull Ollama chat + embedding models per `stack.env.example`; `docker compose --env-file stack.env up -d`
- **stacks/archivebox** — `stack.env.example` → `stack.env`; set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SEARCH_BACKEND_PASSWORD` (and adjust `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` for your Caddy hostnames)
- **stacks/acquire** — optional `stack.env.example` → `stack.env` (e.g. `TZ`). CLI only; mount evidence under `./data`, run `docker compose run --rm acquire /data/evidence.vmdk -o /data/output.tar`. See stack README.
- **stacks/adguard-home** — optional `stack.env.example` → `stack.env`. DNS on host 53/853; web UI via Caddy to adguard-home:3000. Run setup wizard on first visit.
- **stacks/actual-budget** — optional `stack.env.example` → `stack.env` (e.g. `TZ`). No host ports; access via Caddy to actual-budget:5006. Set server URL in Actual desktop/mobile app to your Caddy hostname.
- **stacks/alertmanager** — optional `stack.env.example` → `stack.env`. Copy `alertmanager.yml.example` to `~/.config/alertmanager/alertmanager.yml` and edit for receivers (email, webhooks). No host ports; access via Caddy to alertmanager:9093. Wire Prometheus to `alertmanager:9093`. From Portainer set `ALERTMANAGER_CONFIG_PATH` to the absolute path of that file.
- **stacks/authentik** — `stack.env.example` → `stack.env`; set `AUTHENTIK_SECRET_KEY` (e.g. `openssl rand -base64 50`), `PG_PASS`, `AUTHENTIK_HOST` (e.g. https://authentik.yourdomain.com). Access via Caddy to authentik-server:9000.
- **stacks/archisteamfarm** — create `config/`, copy `ASF.json.example` → `config/ASF.json` and set `IPCPassword` (e.g. `openssl rand -base64 32`); optional `stack.env.example` → `stack.env` for `TZ`, `ASF_UID`. No host ports; access via Caddy (e.g. https://asf.yourdomain.com).
- **stacks/blackbox-exporter** — optional `stack.env.example` → `stack.env`. Copy `blackbox.yml.example` to `~/.config/blackbox-exporter/blackbox.yml` and edit for probe modules. From Portainer set `BLACKBOX_CONFIG_PATH` to the absolute path of that file. No Caddy; Prometheus scrapes blackbox-exporter:9115 on `monitor` network. Add scrape job in Prometheus.
- **stacks/baserow** — `stack.env.example` → `stack.env`; set `BASEROW_PUBLIC_URL` (e.g. https://baserow.yourdomain.com). No host ports; access via Caddy to baserow:80.
- **stacks/bookstack** — `stack.env.example` → `stack.env`; set `APP_URL` (e.g. https://bookstack.yourdomain.com), `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`. Default login admin@admin.com / password — change immediately. Access via Caddy to bookstack:80.
- **stacks/calibre-web** — `stack.env.example` → `stack.env` (optional TZ, PUID, PGID); on first run set Calibre DB path to `/books` in the UI and change default admin password.
- **stacks/caddy** — `stack.env.example` → `stack.env` (for Cloudflare DNS), `Caddyfile.example` → `Caddyfile`
- **stacks/cadvisor** — no config files
- **stacks/cloudflare-tunnel** — `stack.env.example` → `stack.env`, optionally `config.yml.example` → `config.yml`. To put tunnel subdomains behind SSO (e.g. Google/GitHub) instead of basic auth, see [documents/ACCESS-SSO.md](documents/ACCESS-SSO.md).
- **stacks/convertx** — `stack.env.example` → `stack.env`; set `JWT_SECRET` (recommended; `openssl rand -base64 32`); set `ACCOUNT_REGISTRATION=false` after first account
- **stacks/crowdsec** — `stack.env.example` → `stack.env` (optional); use it to set `TZ`, `GID`, and default hub `COLLECTIONS`. See the stack README and CrowdSec Docker docs for configuring acquisitions and bouncers; for Cloudflare edge blocking with the Workers bouncer, see [documents/CROWDSEC-CLOUDFLARE-WORKER.md](documents/CROWDSEC-CLOUDFLARE-WORKER.md).
- **stacks/dependency-track** — `stack.env.example` → `stack.env`; set `POSTGRES_PASSWORD` and `API_BASE_URL` (URL the browser uses for the API, e.g. https://dtrack.home/api). See stack README for Caddy path/subdomain setup.
- **stacks/diun** — `stack.env.example` → `stack.env`; set `DIUN_NOTIF_TELEGRAM_TOKEN` and `DIUN_NOTIF_TELEGRAM_CHATIDS` (or another notifier)
- **stacks/docker-gc** — `stack.env.example` → `stack.env`; by default runs in DRY RUN mode (`DRY_RUN=true`) so you can see which stopped containers and unused images would be removed. Adjust `DRY_RUN`, `DRY_RUN_CONTAINERS`, `DRY_RUN_IMAGES`, and `EXCLUDE_*` as needed before scheduling it.
- **stacks/docker-forensics-toolkit** — optional `stack.env.example` → `stack.env` (e.g. `TZ`). CLI only; build with `docker compose build`, mount forensic disk image under `./data`, run `docker compose run --rm [--privileged] docker-forensics-toolkit mount-image /data/host.raw` then other commands. See stack README.
- **stacks/dozzle** — optional simple auth via `users.yaml` in **`DOZZLE_CONFIG_DIR`** (default **`~/.config/dozzle`**); run **`./prepare-stack.sh`** (see stack README)
- **stacks/explo** — run `./prepare-stack.sh`; set ListenBrainz (`LISTENBRAINZ_USER`), target media system (`EXPLO_SYSTEM`, `SYSTEM_URL`, credentials), and downloader settings (`DOWNLOAD_SERVICES`, `YOUTUBE_API_KEY` for youtube). This is a scheduled worker (no Caddy/HTTP route) that writes downloads under `./data/explo` by default.
- **stacks/firefly-iii** — `stack.env.example` → `stack.env`; set `DB_PASSWORD`, `APP_URL` (e.g. https://firefly-iii.yourdomain.com), `APP_KEY` (generate with `docker run --rm fireflyiii/core php artisan key:generate --show`). Access via Caddy to firefly-iii:8080.
- **stacks/freshrss** — `stack.env.example` → `stack.env`; optional `PUID`, `PGID`, `TZ`
- **stacks/gluetun** — `stack.env.example` → `stack.env`; set `TZ`, `VPN_SERVICE_PROVIDER`, `VPN_TYPE`, and provider-specific vars (e.g. WireGuard keys or OpenVPN user/pass). No HTTP; other containers use it via `network_mode: service:gluetun`. See [Gluetun docs](https://gluetun.com/configuration/).
- **stacks/gitea** — `stack.env.example` → `stack.env`; set `GITEA_DB_PASSWORD`, `GITEA_ROOT_URL` (e.g. https://gitea.yourdomain.com). Access via Caddy to gitea:3000.
- **stacks/grafana** — copy `stack.env.example` → `stack.env`; create `~/.config/grafana/provisioning_dashboards` (copy `provisioning_dashboards.example/default.yaml` and add `json/` subdir; see stack README). Optional: `GF_SERVER_ROOT_URL`, `GRAFANA_DATASOURCES_PATH`, `GRAFANA_DASHBOARDS_PATH`; TZ/locale via shared.env
- **stacks/guacamole** — `stack.env.example` → `stack.env`; set `POSTGRES_PASSWORD` (strong random; shared by Postgres and the Guacamole web app); optional `POSTGRES_DB`, `POSTGRES_USER`, and `TZ`. Access via Caddy only.
- **stacks/harbor** — No stack.env in this repo; use the official Harbor installer and generated compose (see stacks/harbor/README.md).
- **stacks/headscale** — `stack.env.example` → `stack.env`; create `config.yaml` from `config.example.yaml`, then set `HEADSCALE_CONFIG_B64` to its base64 (e.g. `base64 -w 0 config.yaml`) in `stack.env` or in Portainer stack env
- **stacks/homepage** — optional `stack.env.example` → `stack.env`. Static files in `./www`; edit `www/index.html` for content. No host ports; access via Caddy at your root domain (e.g. yourdomain.com, www.yourdomain.com) or homepage.yourdomain.com.
- **stacks/homarr** — optional `stack.env.example` → `stack.env` (e.g. `TZ`). No host ports; access via Caddy to homarr:7575.
- **stacks/home-assistant** — optional `stack.env.example` → `stack.env`. No host ports; access via Caddy to home-assistant:8123.
- **stacks/hedgedoc** — `stack.env.example` → `stack.env`; set `POSTGRES_PASSWORD`, `CMD_DOMAIN` (e.g. hedgedoc.yourdomain.com). Access via Caddy to hedgedoc:3000.
- **stacks/immich** — `stack.env.example` → `stack.env`; set `DB_PASSWORD` (and optionally `TZ`, OAuth via Admin UI)
- **stacks/komga** — `stack.env.example` → `stack.env` (optional TZ, JAVA_TOOL_OPTIONS); create first user in the web UI, then add libraries (default `/data` or bind-mount).
- **stacks/kavita** — `stack.env.example` → `stack.env` (optional TZ, PUID, PGID); run setup wizard in the web UI and add libraries (e.g. `/data` or bind-mount).
- **stacks/infisical** — `stack.env.example` → `stack.env`; set `ENCRYPTION_KEY`, `AUTH_SECRET`, `POSTGRES_PASSWORD`, `SITE_URL` (e.g. `https://infisical.home` or `https://secrets.yourdomain.com`)
- **stacks/librechat** — `./prepare-stack.sh` or `stack.env.example` → `stack.env`; set `JWT_SECRET`, `JWT_REFRESH_SECRET` (e.g. `openssl rand -base64 32`); set `MONGO_INITDB_ROOT_PASSWORD`, `REDIS_PASSWORD`; set `DOMAIN_CLIENT` / `DOMAIN_SERVER` and `OLLAMA_BASE_URL` for Caddy + Ollama
- **stacks/litellm** — `./prepare-stack.sh`; set `LITELLM_MASTER_KEY`, `POSTGRES_PASSWORD`, `UI_*`; edit `litellm_config.yaml` for providers; `docker compose up -d` (bundled Postgres; see stack README)
- **stacks/linkstack** — `stack.env.example` → `stack.env` (all vars optional); optional `HTTP_SERVER_NAME` / `HTTPS_SERVER_NAME` when behind Caddy
- **stacks/lanraragi** — `stack.env.example` → `stack.env` (optional TZ, LRR_UID, LRR_GID); upload or drop archives in the web UI or content volume.
- **stacks/linkwarden** — `stack.env.example` → `stack.env`; set `NEXTAUTH_SECRET`, `POSTGRES_PASSWORD`, `MEILI_MASTER_KEY` (and `NEXTAUTH_URL` if behind Caddy)
- **stacks/linkding** — optional `stack.env.example` → `stack.env` (e.g. `TZ`). No host ports; access via Caddy to linkding:9090.
- **stacks/loki** — Copy `loki-config.yml.example` to `~/.config/loki/loki-config.yml` (create dir if needed). From Portainer set `LOKI_CONFIG_PATH` to that absolute path. Optional `stack.env` for `TZ`. No Caddy; add Loki as data source in Grafana (http://loki:3100).
- **stacks/logseq-sync** — Experimental; run `./clone-repo.sh`, then build and run. See stack README.
- **stacks/maigret** — no required env; optional TZ. Deploy and access via Caddy (e.g. https://maigret.home)
- **stacks/mailpit** — no config required. Deploy and add Caddy block for mailpit.yourdomain.com. For internal-only mail, set Postfix `RELAYHOST=mailpit:1025` in `stacks/postfix/stack.env`.
- **stacks/mealie** — `stack.env.example` → `stack.env`; set `BASE_URL` if behind Caddy, `ALLOW_SIGNUP` (false after first account)
- **stacks/meilisearch** — `stack.env.example` → `stack.env`; when exposing via Caddy set `MEILI_MASTER_KEY` (e.g. `openssl rand -hex 32`) and `MEILI_ENV=production`. No host ports; access via Caddy to meilisearch:7700.
- **stacks/minio** — `stack.env.example` → `stack.env`; set `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` (e.g. `openssl rand -hex 16`, `openssl rand -base64 32`); optional `MINIO_SERVER_URL`. Access via Caddy to minio:9001 (console).
- **stacks/mylar3** — `stack.env.example` → `stack.env` (optional TZ, PUID, PGID). Set `MYLAR3_MEDIA_PATH`, configure NZBGet/qBittorrent/Prowlarr, and use `/data/comics` as Comic Location.
- **stacks/mosquitto** — optional `stack.env.example` → `stack.env`. MQTT on host 1883; create `mosquitto.conf` in config volume. Used by Zigbee2MQTT, Home Assistant, Node-RED.
- **stacks/n8n** — `stack.env.example` → `stack.env`; set `N8N_HOST` and `WEBHOOK_URL` to your Caddy URL (e.g. https://n8n.home or https://n8n.yourdomain.com); optional `N8N_ENCRYPTION_KEY`
- **stacks/ntfy** — `stack.env.example` → `stack.env`; set `NTFY_BASE_URL` (e.g. https://ntfy.yourdomain.com). No host ports; access via Caddy to ntfy:80.
- **stacks/ntopng** — optional `stack.env.example` → `stack.env`. Uses host networking; web UI on host :3000. Optional Caddy block to host.docker.internal:3000.
- **stacks/naisho** — `stack.env.example` → `stack.env`; set `SECRET_KEY_BASE` (`openssl rand -hex 64`); stack builds from GitHub on first deploy; configure SMTP in the app when sending deletion emails
- **stacks/navidrome** — `stack.env.example` → `stack.env`; optional `TZ`; optional `ND_BASEURL` (when behind Caddy, set to your full Navidrome URL, e.g. https://music.yourdomain.com); optional `ND_LOGLEVEL`, `ND_SCANSCHEDULE`, and other `ND_` options (see Navidrome docs)
- **stacks/nextcloud** — `stack.env.example` → `stack.env`; set `POSTGRES_PASSWORD`, `NEXTCLOUD_ADMIN_PASSWORD`, `NEXTCLOUD_TRUSTED_DOMAINS` (e.g. nextcloud.yourdomain.com). Access via Caddy to nextcloud:80.
- **stacks/netbox** — Pointer stack; use upstream netbox-docker. Attach to `monitor` network and add Caddy block for netbox.yourdomain.com. See stack README.
- **stacks/nzbget** — `stack.env.example` → `stack.env`; set `TZ`, `PUID`, `PGID`, optional `UMASK`, and optionally `NZBGET_USER`/`NZBGET_PASS` for the web UI. Configure Usenet servers in the NZBGet UI.
- **stacks/nzbhydra2** — `stack.env.example` → `stack.env`; set `TZ`, `PUID`, `PGID`, optional `UMASK`. Configure upstream indexers and API key in the NZBHydra 2 UI.
- **stacks/ollama** — `./prepare-stack.sh` or `stack.env.example` → `stack.env`; optional `OLLAMA_MODELS_PATH` (absolute path recommended for models); other data uses Docker volume; compose includes NVIDIA `deploy` (comment it out on CPU-only hosts without the toolkit); GPU needs NVIDIA Container Toolkit + Docker runtime config
- **stacks/onionprobe** — run `./clone-repo.sh` once to clone the upstream repo into `./repo`; optional `stack.env` for `GRAFANA_DATABASE_PASSWORD`, `GF_SERVER_ROOT_URL`; access via Caddy (onionprobe.home → Grafana)
- **stacks/onionscan** — CLI only; no web UI or ports. Optional: `stack.env` with TZ. Start with `docker compose up -d`, wait for Tor (logs), then `docker compose exec onionscan onionscan [options] <onion-address>`. See stack README.
- **stacks/outline** — `stack.env.example` → `stack.env`; set `POSTGRES_PASSWORD`, `URL` (e.g. https://outline.yourdomain.com), `SECRET_KEY`, `UTILS_SECRET`, and S3 vars if using MinIO. Create bucket in MinIO. Access via Caddy to outline:3000.
- **stacks/open-notebook** — run `./prepare-stack.sh`; set `OPEN_NOTEBOOK_ENCRYPTION_KEY` (e.g. `openssl rand -base64 32`), `SURREAL_PASSWORD`, and `API_URL` (must match your Caddy hostname, e.g. https://notebook.yourdomain.com); optional `OLLAMA_BASE_URL`
- **stacks/open-webui** — `stack.env.example` → `stack.env`; set `OLLAMA_BASE_URL` to reach Ollama (e.g. `http://ollama:11434` or `http://host.docker.internal:11434`); optional `OPENAI_API_BASE_URL` + `OPENAI_API_KEY` for **litellm** (see stack README / ENV-VARS)
- **stacks/paperless-ngx** — `stack.env.example` → `stack.env`; set `PAPERLESS_URL`, `PAPERLESS_SECRET_KEY`
- **stacks/paperless-ai-next** — `./prepare-stack.sh`; external volume `paperless-ai-next_paperless_ai_next_data` must exist; `stack.env` per `stack.env.example`; `docker compose --env-file stack.env up -d`
- **stacks/paperless-gpt** — `./prepare-stack.sh`; external volumes for prompts/hocr/pdf must exist; `stack.env` per `stack.env.example`; `docker compose --env-file stack.env up -d`
- **stacks/password-pusher** — `stack.env.example` → `stack.env`; set `PWPUSH_MASTER_KEY` (generate at https://us.pwpush.com/generate_key); optional `PWP__HOST_DOMAIN` if behind Caddy
- **stacks/perplexica** — `stack.env.example` → `stack.env`; optional `PERPLEXICA_DATA_PATH`, `SEARXNG_API_URL`, `OLLAMA_BASE_URL`
- **stacks/picard** — run `./prepare-stack.sh`; optionally set `PUID`/`PGID`, then confirm `PICARD_MEDIA_PATH` (default `/mnt/unraid/media`). Use `/data/downloads/...` for intake and `/data/music` for output. Access via Caddy to `picard:5800`.
- **stacks/plex** — `stack.env.example` → `stack.env`; set `TZ`, `PUID`, `PGID`, `VERSION=docker`, and optionally `PLEX_CLAIM` (from Plex) on first run to link the server to your account.
- **stacks/plaso** — optional `stack.env.example` → `stack.env` (e.g. `TZ`). CLI only; mount evidence under `./data` and run `docker compose run --rm plaso log2timeline ...` / `psort ...`. See stack README.
- **stacks/privotron** — `./prepare-stack.sh` or `cp stack.env.example stack.env`; `docker compose build` (no upstream image); then `docker compose run --rm privotron --profile NAME` (create profile with `--save-profile`). Optional: `PRIVOTRON_VERSION` in stack.env when building; mount `./brokers` for `.skipbrokers`. See stack README.
- **stacks/prometheus** — copy `prometheus.yml.example` to `~/.config/prometheus/prometheus.yml` and `alerts.yml.example` to `~/.config/prometheus/rules/alerts.yml` (create both dirs if needed); when deploying from Portainer set `PROMETHEUS_CONFIG_PATH` and `PROMETHEUS_RULES_PATH` to the absolute paths of that file and the rules directory; no secrets
- **stacks/promtail** — Copy `promtail-config.yml.example` to `~/.config/promtail/promtail-config.yml` (create dir if needed). Deploy after Loki; from Portainer set `PROMTAIL_CONFIG_PATH` to that absolute path. Optional `stack.env`. No Caddy; ships logs to http://loki:3100 on `monitor`.
- **stacks/qbittorrent** — `stack.env.example` → `stack.env`; set `TZ`, `PUID`, `PGID`, `QBITTORRENT_MEDIA_PATH`; configure Gluetun VPN (`VPN_SERVICE_PROVIDER`, `VPN_TYPE`, and provider-specific vars, e.g. WireGuard keys). Use `/data/downloads/torrents` as qBittorrent's save path. See stack README and [Gluetun docs](https://gluetun.com/configuration/).
- **stacks/searx-ng** — `./prepare-stack.sh` or `stack.env.example` → `stack.env`; set `SEARXNG_SECRET`, `SEARXNG_BASE_URL` (must match the public Caddy URL), and optionally `SEARXNG_SETTINGS_PATH` (default `~/.config/searx-ng/settings.yml`); deploy with `docker compose --env-file stack.env up -d` so volume paths interpolate correctly
- **stacks/scrutiny** — `stack.env.example` → `stack.env` (optional TZ). Runs privileged for SMART/device access; adjust `devices` in compose if needed. Access via Caddy to scrutiny:8080.
- **stacks/seafile** — `stack.env.example` → `stack.env`; set `MYSQL_ROOT_PASSWORD`, `SEAFILE_DB_PASSWORD`, `SEAFILE_SERVER_HOSTNAME` (e.g. seafile.yourdomain.com). Access via Caddy to seafile:80.
- **stacks/simplelogin** — `stack.env.example` → `stack.env`; create `data/dkim.key` (see README); set `URL`, `EMAIL_DOMAIN`, `EMAIL_SERVERS_WITH_PRIORITY`, `SUPPORT_EMAIL`, `FLASK_SECRET` (`openssl rand -hex 32`), `POSTGRES_PASSWORD`; run migration and init once (see stack README)
- **stacks/shlink** — `stack.env.example` → `stack.env`; set `DEFAULT_DOMAIN` (e.g. short.yourdomain.com) to match Caddy hostname, `GEOLITE_LICENSE_KEY` (free at MaxMind); optional `INITIAL_API_KEY` (e.g. `openssl rand -hex 32`). Access via Caddy to shlink:8080; manage short URLs at app.shlink.io with server URL and API key.
- **stacks/slink** — `stack.env.example` → `stack.env`; set `ORIGIN` to your Caddy URL (e.g. https://slink.home or https://slink.yourdomain.com)
- **stacks/snipe-it** — `stack.env.example` → `stack.env`; set `APP_KEY` (`openssl rand -base64 32`), `DB_PASSWORD`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `APP_URL` (e.g. https://snipe-it.yourdomain.com). Optional MAIL_* for Postfix. Access via Caddy to snipeit:80.
- **stacks/syncthing** — `stack.env.example` → `stack.env` (optional TZ). Access via Caddy to syncthing:8384.
- **stacks/sonarr** — `stack.env.example` → `stack.env`; set `TZ`, `PUID`, `PGID`. Configure NZBGet/qBittorrent and Prowlarr/NZBHydra 2 in the Sonarr UI.
- **stacks/soulseek** — run `./prepare-stack.sh`; then set `SLSKD_SLSK_USERNAME` and `SLSKD_SLSK_PASSWORD` in `stack.env` (and optionally `SLSKD_SLSK_LISTEN_PORT`, default `50300`). Forward that TCP/UDP peer port from your router/firewall if you want inbound peers. Access web UI via Caddy to soulseek:5030.
- **stacks/stirling-pdf** — optional `stack.env.example` → `stack.env` (e.g. `TZ`). No host ports; access via Caddy to stirling-pdf:8080.
- **stacks/stoat** — no `stack.env.example`; from the stack directory, download and run `generate_config.sh` from `stoatchat/self-hosted` to create `.env.web`, `Revolt.toml`, and `livekit.yml`; then optionally change `HOSTNAME=:80` in `.env.web` when running behind this repo’s main Caddy; see stack README and upstream docs for advanced config
- **stacks/threat-dragon** — `stack.env.example` → `stack.env`; set `SESSION_SIGNING_KEY` (e.g. `openssl rand -hex 16`); for repo storage set GitHub/Bitbucket/GitLab OAuth vars. See stack README.
- **stacks/torbot** — CLI only (OWASP TorBot). No ports. Optional: `stack.env` with TZ. Start with `docker compose up -d`, wait for Tor (`docker compose logs -f tor`), then `docker compose exec torbot torbot -u <url> --host tor --port 9050 [options]`. See stack README.
- **stacks/umami** — `./prepare-stack.sh` or `stack.env.example` → `stack.env`; set `POSTGRES_PASSWORD` and `APP_SECRET` (`openssl rand -base64 32`); `./prepare-stack.sh` copies `stack.env` → `.env` so Compose substitutes `${VAR}` in `DATABASE_URL`. Edit `caddy_snippet.conf`, reload Caddy. Default login admin / umami — change immediately. Access via Caddy to umami:3000.
- **stacks/vaultwarden** — `stack.env.example` → `stack.env`; set `DOMAIN` if behind Caddy, `SIGNUPS_ALLOWED` (false after first account)
- **stacks/vector** — optional `stack.env.example` → `stack.env`. Log shipper to Loki (http://loki:3100); ensure Loki stack is on `monitor` network. No Caddy.
- **stacks/vikunja** — `stack.env.example` → `stack.env`; set `VIKUNJA_SERVICE_PUBLICURL` (e.g. https://vikunja.yourdomain.com/ with trailing slash). No host ports; access via Caddy to vikunja:3456.
- **stacks/woodpecker-ci** — `stack.env.example` → `stack.env`; set `POSTGRES_PASSWORD`, `WOODPECKER_DATABASE_DATASOURCE` (same password), `WOODPECKER_GITEA_URL`, `WOODPECKER_GITEA_CLIENT`, `WOODPECKER_GITEA_SECRET`, `WOODPECKER_AGENT_SECRET`. Create OAuth app in Gitea. Access via Caddy to woodpecker-server:8000.
- **stacks/wireguard** — `stack.env.example` → `stack.env`; set `TZ`, `PUID`, `PGID`, `SERVERURL` (public IP or DNS, or `auto`), `SERVERPORT` (51820), `PEERS`. Forward UDP 51820 on your router. No Caddy hostname. See stack README.
- **stacks/web-check** — optional: `stack.env.example` → `stack.env` for API keys
- **stacks/whisper-asr** — `./prepare-stack.sh`; tune `ASR_MODEL` / `ASR_ENGINE` in `stack.env`; `docker compose --env-file stack.env up -d` (GPU: see stack README)
- **stacks/watchtower** — TZ, LANG, LC_ALL, LC_CTYPE in `stack.env` if you choose to override defaults
- **stacks/yourls** — `stack.env.example` → `stack.env`; set `YOURLS_SITE` (e.g. https://short.home or https://short.yourdomain.com) to match Caddy hostname; set `YOURLS_USER`, `YOURLS_PASS`, `YOURLS_COOKIEKEY`, `YOURLS_DB_PASSWORD`, `YOURLS_DB_ROOT_PASSWORD`
- **stacks/zed-attack-proxy** — Optional: `stack.env` with TZ. No host ports; access via Caddy (e.g. https://zap.home). See stack README.
- **stacks/zigbee2mqtt** — `stack.env.example` → `stack.env`; set `ZIGBEE2MQTT_CONFIG_MQTT_SERVER` (e.g. mqtt://mosquitto:1883). Adjust device path in compose if needed. Access via Caddy to zigbee2mqtt:8080.
- **stacks/bazarr** — `stack.env.example` → `stack.env`; set `TZ`, `PUID`, `PGID`. Wire to Sonarr and Radarr in the Bazarr UI and configure subtitle providers.
- **stacks/jellyfin** — `stack.env.example` → `stack.env`; set `TZ`, `PUID`, `PGID`. Configure libraries for `/data/tv`, `/data/movies`, `/data/music` in the Jellyfin UI.
- **stacks/kasm** — optional `stack.env.example` → `stack.env` (DOCKER_HUB_*, DOCKER_MTU). No host ports; access via Caddy to kasm:443 (main UI) and kasm:3000 (setup wizard). Complete setup wizard at kasm-setup.yourdomain.com first; then set Proxy Port to 0 in Admin → Zones. Requires privileged mode (DinD).
- **stacks/joplin-server** — `stack.env.example` → `stack.env`; set `POSTGRES_PASSWORD`, `APP_BASE_URL` (e.g. https://joplin.yourdomain.com). Access via Caddy to joplin-server:22300.
- **stacks/keycloak** — `stack.env.example` → `stack.env`; set `POSTGRES_PASSWORD`, `KEYCLOAK_ADMIN_PASSWORD`, `KC_HOSTNAME` (e.g. https://keycloak.yourdomain.com). Access via Caddy to keycloak:8080.
- **stacks/kokoro-tts** — `./prepare-stack.sh`; optional `KOKORO_IMAGE_TAG` / `API_LOG_LEVEL` in `stack.env`; `docker compose --env-file stack.env up -d` (GPU: see stack README)
- **stacks/lidarr** — `stack.env.example` → `stack.env`; set `TZ`, `PUID`, `PGID`. Wire to NZBGet/qBittorrent and Prowlarr/NZBHydra 2 in the Lidarr UI.
- **stacks/prowlarr** — `stack.env.example` → `stack.env`; set `TZ`, `PUID`, `PGID`. Configure indexers and app sync for Sonarr/Radarr/Lidarr/Readarr in the Prowlarr UI.
- **stacks/radarr** — `stack.env.example` → `stack.env`; set `TZ`, `PUID`, `PGID`. Wire to NZBGet/qBittorrent and Prowlarr/NZBHydra 2 in the Radarr UI.
- **stacks/readarr** — `stack.env.example` → `stack.env`; set `TZ`, `PUID`, `PGID`. Wire to NZBGet/qBittorrent and Prowlarr/NZBHydra 2 in the Readarr UI.
- **stacks/whisparr** — `stack.env.example` → `stack.env`; set `WHISPARR_*_PATH` bind paths and `PUID`/`PGID`/`TZ`. Deploy with **`docker compose --env-file stack.env up -d`** so compose can substitute volume paths. Image `ghcr.io/thespad/whisparr` (port 6969); `usenet`/`torrents` networks match other acquisition stacks.
- **stacks/restic** — `./prepare-stack.sh` or `cp stack.env.example stack.env`; set `RESTIC_REPOSITORY` (e.g. s3:http://minio:9000/restic), `RESTIC_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`; set `RESTIC_PATH_DOCKER` and `RESTIC_PATH_MEDIA` for backup paths (or edit compose). CLI/cron only; no Caddy.
- **stacks/romm** — `stack.env.example` → `stack.env`; set `ROMM_AUTH_SECRET_KEY` (`openssl rand -hex 32`), `MARIADB_ROOT_PASSWORD`, `MARIADB_PASSWORD`, `ROMM_BASE_URL` (e.g. https://romm.yourdomain.com); add `config.yml` to config volume or bind-mount (see [RomM config](https://docs.romm.app/latest/Getting-Started/Configuration-File/)).
- **stacks/rtorrent-flood** — `stack.env.example` → `stack.env`; set `TZ`, `PUID`, `PGID`, optional `UMASK`. Configure Flood and rTorrent settings via the web UI; downloads land in the `torrents_manual` volume.

### 2. 🔗 Shared resources and one-time setup

Networks (`monitor`, `torrents`, `usenet`), **MinIO**, **Postfix**, and **Ollama** are shared across stacks where applicable. For a one-time setup checklist and optional optimizations (e.g. **shared env file** for TZ/locale, shared Redis), see **[documents/SHARED-RESOURCES.md](documents/SHARED-RESOURCES.md)**.

### 3. 📊 Step-by-step: Grafana & Prometheus integration

To bring up metrics collection and dashboards, bring these stacks online in order. All use the shared **`monitor`** network so Caddy can reverse-proxy to them and Prometheus can scrape targets.

| Step | Stack | Purpose | Notes |
|------|--------|---------|--------|
| **0** | **Create network** | One-time | From the `docker/` repo root: `docker network create monitor` (if not already present). |
| **1** | **Caddy** | HTTP(S) entrypoint | Must be running so you can reach Grafana and Prometheus UIs by hostname. If Caddy is already up, skip. |
| **2** | **Prometheus** | Metrics storage | Copy `prometheus.yml.example` to `~/.config/prometheus/prometheus.yml`, then `cd stacks/prometheus && docker compose up -d`. No secrets. |
| **3** | **cAdvisor** | Container metrics | `cd stacks/cadvisor && docker compose up -d`. Prometheus scrapes `cadvisor:8080` (already in the example config). |
| **4** | **Grafana** | Dashboards | `cd stacks/grafana && cp stack.env.example stack.env && docker compose up -d`. Open via Caddy (e.g. https://grafana.yourdomain.com). Default login `admin` / `admin`; change on first use. Prometheus (and Loki, if deployed) are provisioned via `datasources.yml.example`. |
| **Optional** | **Alertmanager** | Alert routing | Deploy `stacks/alertmanager`; `prometheus.yml.example` already includes an `alerting` block to `alertmanager:9093`. Configure receivers in `~/.config/alertmanager/alertmanager.yml` (example enables ntfy webhook). |
| **Optional** | **ntfy** | Push notifications | Deploy `stacks/ntfy` on `monitor`; set `NTFY_BASE_URL` to your Caddy URL. Subscribe to the topic used in Alertmanager (e.g. `alerts`) in the ntfy app to receive alerts. |
| **Optional** | **Blackbox exporter** | Synthetic probes | For HTTP/TCP/ICMP probes: deploy `stacks/blackbox-exporter`, then add a scrape job in `prometheus.yml` for `blackbox-exporter:9115`. |
| **Optional** | **Loki** | Log aggregation | Deploy `stacks/loki` (copy `loki-config.yml.example` to `~/.config/loki/loki-config.yml`). Grafana’s provisioned datasources include Loki; use **Explore** → **Loki** to query. |
| **Optional** | **Alloy** | Docker log shipper | Deploy `stacks/alloy` after Loki. Alloy owns Docker container discovery and shipping in the current baseline. |
| **Optional** | **Promtail** | Host log shipper | Deploy `stacks/promtail` after Loki; copy config to `~/.config/promtail/promtail-config.yml`. It handles host files and journald, avoiding duplicate Docker ingestion with Alloy. |
| **Alternative** | **Vector** | Log shipper | Deploy Vector only when intentionally using it instead of the baseline shippers; avoid collecting the same source twice. |

Grafana provisions the repository's datasources and dashboards when its example
configuration is installed. External dashboards such as IDs **893** (cAdvisor)
and **3662** (Prometheus overview) remain optional. See
[stacks/grafana/README.md](stacks/grafana/README.md).

### 4. ⚙️ Shared settings

For timezone, locale, and optional per-app settings, see **[documents/ENV-VARS.md](documents/ENV-VARS.md)**.

### 5. ▶️ Deploy

From a stack directory: `docker compose up -d` (each stack’s compose loads `stack.env` via `env_file` where applicable). If a stack has no `env_file`, use `docker compose --env-file stack.env up -d` or set variables in Portainer. You can also add the stack in Portainer (Git deploy so bind-mounted config files are present).

---

## 💚 Health endpoints (Uptime Kuma)

These stacks expose a dedicated health/status URL so you can monitor them without hitting the main page:

| Stack | Endpoint |
|-------|----------|
| **alertmanager** | `/-/healthy` |
| **anything-llm** | (use HTTP check to app URL) |
| **audiobookshelf** | `/healthcheck` |
| **cadvisor** | `/healthz` |
| **convertx** | (use HTTP check to app URL) |
| **grafana** | `/api/health` |
| **headscale** | `/health` |
| **immich** | `/api/server/ping` |
| **kokoro-tts** | `/docs` (FastAPI OpenAPI; UI at `/web`) |
| **librechat** | (use HTTP check to app URL) |
| **litellm** | `/health/liveliness` (upstream spelling) |
| **loki** | `http://loki:3100/ready` (internal; no Caddy) |
| **mealie** | `/api/app/about` |
| **mattermost** | `/api/v4/system/ping` |
| **n8n** | `/healthz` |
| **naisho** | `/up` |
| **navidrome** | (no dedicated health endpoint; use HTTP check to app URL, e.g. `https://music.yourdomain.com/`) |
| **ntfy** | (use HTTP check to app URL, e.g. `https://ntfy.yourdomain.com`) |
| **ollama** | (API only; use HTTP check to `http://ollama:11434` or `/api/tags`) |
| **open-notebook** | (use HTTP check to app URL) |
| **open-webui** | (use HTTP check to app URL) |
| **password-pusher** | `/up` |
| **perplexica** | (use HTTP check to app URL) |
| **prometheus** | `/-/healthy` |
| **promtail** | `http://promtail:9080/ready` (internal; no Caddy) |
| **shlink** | `/rest/v3/health` (or use HTTP check to app URL) |
| **slink** | (use HTTP check to app URL) |
| **umami** | `/api/heartbeat` |
| **vaultwarden** | `/alive` |
| **whisper-asr** | (use HTTP check to app URL, e.g. `/` on port 9000) |
| **yourls** | (no dedicated health endpoint; use HTTP check to app URL) |

Other stacks (paperless-ngx, linkwarden, searx-ng, linkstack, caddy, infisical, romm, komga, calibre-web, mylar3, kavita, lanraragi, etc.) have no dedicated health endpoint; use an HTTP check to the app URL if needed. Keep this table alphabetized by stack name when adding new entries.

---

## 📁 Layout

The repo has a fixed top-level structure; the full list of stacks comes from the filesystem:

- **portainer/** — Portainer CE stack (Docker management UI).
- **stacks/** — One directory per stack (e.g. `stacks/caddy/`, `stacks/immich/`). Each contains a README, `stack.env.example`, `stack.yaml`, and its deployment files. See the [stack catalog](documents/STACK-CATALOG.md) for the full list.
- **documents/** — ENV-VARS.md, ACCESS-SSO.md, and other guides.
- **.gitignore** — Excludes `.env`, `stack.env`, `config.yml`, `Caddyfile`, and other sensitive or generated files.

To print an up-to-date tree of all stack directories, run from the `docker/` repo root:

```bash
./scripts/list-layout.sh
```

---

## 🧱 Adding or updating a stack

When you add a new stack or update an existing one, follow these conventions so docs and infra stay in sync:

- **Name & directory**: Use the primary service name in kebab-case (e.g. `immich`, `grafana`), and create `stacks/<stack-name>/` with at least `docker-compose.yml`, `README.md`, and optionally `stack.env.example`.
- **Environment files**: Load per-stack config from `stack.env` via `env_file` in compose. For `TZ`, `LANG`, `LC_ALL`, and `LC_CTYPE` prefer the shared `shared.env` file (see `documents/SHARED-RESOURCES.md`) instead of duplicating them in each `stack.env.example`—add a short comment in new `stack.env.example` files pointing to that doc.
- **Hostnames & Caddy**: In committed files (READMEs, examples, Caddy snippets) use only placeholder hostnames like `<stack-name>.yourdomain.com`; set your real domain in local, gitignored files (`stack.env`, `Caddyfile`, etc.). Wire HTTP(S) through Caddy on the `monitor` network rather than binding app ports directly.
- **Docs to update**: When you add a stack, update:
  - The generated stack catalog (`python3 scripts/build-stack-catalog.py`).
  - The **“Secrets and config”** list in this README.
  - `documents/ENV-VARS.md` (add an entry under “Already set in these stacks”, keep the list alphabetized).
  - `documents/ACCESS-SSO.md` if the stack is exposed via tunnel and you care about SSO.
  - The **Health endpoints** table above if the app has a dedicated health path.
  - `documents/topology.yaml` (then re-run `python3 scripts/build-topology.py --in-place`) if the new stack meaningfully changes the high-level topology.
