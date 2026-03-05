# Common environment variables (Docker host stacks)

Use these as a checklist when adding new stacks. Not every image respects all of them.

## Locale & timezone (example: Denver, UTF-8)

```yaml
environment:
  - TZ=America/Denver
  - LANG=en_US.UTF-8
  - LC_ALL=en_US.UTF-8
  - LC_CTYPE=en_US.UTF-8
```

- **TZ** – Logs and in-app times. Set to your timezone (e.g. `America/Denver`, `Europe/London`).
- **LANG / LC_ALL** – Default locale and encoding (UTF-8).
- **LC_CTYPE** – Character classification (UTF-8); some apps use it for filenames and text.

## Optional (per-app)

- **LANGUAGE** – Message language, e.g. `en_US:en` (if the image shows translated messages).
- **PYTHONIOENCODING** – For Python apps: `UTF-8` so stdin/stdout/stderr are UTF-8.
- **NODE_OPTIONS** – For Node apps, e.g. `--max-old-space-size=512` if you need to cap memory.
- **PUID / PGID** – Some images (e.g. LinuxServer.io) use these to run as a specific user; set to your host user if you want file ownership to match.
- **UMASK** – e.g. `0022` or `0002` if the image documents it for volume file permissions.

## Already set in these stacks

- **ail** – TZ (optional). AIL framework (Analysis Information Leak); uses community image cciucd/ail-framework. No host ports; access via Caddy only (backend HTTPS on 7000; Caddy uses tls_insecure_skip_verify). Resource-heavy: >6GB RAM recommended. See stack README.
- **archivebox** – TZ, LANG, LC_ALL, LC_CTYPE; ADMIN_USERNAME, ADMIN_PASSWORD, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, SEARCH_BACKEND_PASSWORD; optional PUBLIC_INDEX, PUBLIC_SNAPSHOTS, PUBLIC_ADD_VIEW.
- **acquire** – TZ (optional). CLI only; forensic artifact collection (Acquire/Dissect). Mount evidence to `/data`; run via `docker compose run --rm acquire [target] -o /data/output.tar`. See stack README.
- **asf** – TZ (optional); ASF_UID (optional, for volume file ownership). Config is file-based: `config/ASF.json` (Kestrel `http://0.0.0.0:1242`, IPCPassword required when exposing IPC). No host ports; access via Caddy to asf:1242. See stack README and [ASF Configuration](https://github.com/JustArchiNET/ArchiSteamFarm/wiki/Configuration).
- **audiobookshelf** – TZ (optional). Image does not use PUID/PGID; for bind-mounted audiobooks/podcasts ensure host dir is readable by the container user (e.g. `chown -R 1000:1000 /path`). See stack README.
- **bazarr** – TZ, PUID, PGID (optional). Uses media paths `/tv` and `/movies` to manage subtitles; configure providers in the Bazarr UI.
- **blackbird** – TZ (optional). OSINT CLI; optional env for output paths and report options. See stack README.
- **calibre-web** – TZ (optional); PUID, PGID (optional, default 1000). LinuxServer image; Calibre library at `/books` (named volume or bind-mount). No host ports; access via Caddy to calibre-web:8083. Optional SECRET_KEY (cookie encryption), DOCKER_MODS (ebook conversion, x86-64), OAUTHLIB_RELAX_TOKEN_SCOPE (Google OAuth). See [LinuxServer Calibre-Web](https://docs.linuxserver.io/images/docker-calibre-web) and stack README.
- **caddy** – TZ, LANG, LC_ALL, LC_CTYPE.
- **cadvisor** – TZ, LANG, LC_ALL, LC_CTYPE; no config files.
- **cloudflare-tunnel** – TZ, LANG, LC_ALL, LC_CTYPE.
- **convertx** – TZ (optional); JWT_SECRET (recommended; e.g. `openssl rand -base64 32`); ACCOUNT_REGISTRATION (false after first account); HTTP_ALLOWED, LANGUAGE, AUTO_DELETE_EVERY_N_HOURS, etc. See stack `stack.env.example`.
- **crowdsec** – TZ (optional); GID (group ID CrowdSec runs as inside the container so it can read your logs); COLLECTIONS (default hub collections to install, e.g. `crowdsecurity/linux`). See the CrowdSec stack README and Docker installation docs for acquisitions and bouncers.
- **dependency-track** – TZ (optional); API_BASE_URL (required; URL the browser uses for the API, e.g. https://dtrack.home/api); POSTGRES_PASSWORD, POSTGRES_USER, POSTGRES_DB. No host ports; Caddy reverse-proxies to dtrack-frontend:8080 and dtrack-apiserver:8080. See stack README for path vs subdomain.
- **diun** – TZ, LANG, LC_ALL, LC_CTYPE; DIUN_WATCH_*, DIUN_PROVIDERS_DOCKER; DIUN_NOTIF_* for notifiers (see stack `stack.env.example`).
- **docker-gc** – Optional TZ, LANG, LC_ALL, LC_CTYPE; maintenance job that talks to the host Docker daemon via `/var/run/docker.sock`. Uses `DRY_RUN` (global), `DRY_RUN_CONTAINERS`, and `DRY_RUN_IMAGES` to control whether containers/images are actually removed or just logged, plus `EXCLUDE_IMAGES` and `EXCLUDE_CONTAINERS` to protect specific resources. Also reads `/etc/docker-gc-exclude` and `/etc/docker-gc-exclude-containers` on the host for file-based patterns.
- **docker-forensics-toolkit** – TZ (optional); optional DOF_IMAGE_MOUNTPOINT. CLI only; post-mortem analysis of Docker host disk images. Build with `docker compose build`; run `mount-image`, `list-containers`, etc. Mounting may require `--privileged`. See stack README.
- **dozzle** – TZ, LANG, LC_ALL, LC_CTYPE; optional DOZZLE_AUTH_PROVIDER, DOZZLE_AUTH_USERNAME, DOZZLE_AUTH_PASSWORD.
- **emby** – TZ; PUID, PGID. Media libraries use `/data/tv`, `/data/movies`, `/data/music`; enable hardware-accelerated transcoding in the Emby UI when NVIDIA support is configured on the host.
- **freshrss** – TZ, PUID, PGID (optional).
- **ghunt** – TZ (optional). OSINT CLI for Google account investigation; optional env for output. See stack README.
- **gluetun** – TZ (optional); VPN_SERVICE_PROVIDER, VPN_TYPE; provider-specific (e.g. WIREGUARD_* or OPENVPN_*). No HTTP; used by other containers via `network_mode: service:gluetun`. See [Gluetun configuration](https://gluetun.com/configuration/) and stack `stack.env.example`.
- **grafana** – TZ, LANG, LC_ALL, LC_CTYPE; optional GF_SERVER_ROOT_URL (when behind Caddy), GF_USERS_ALLOW_SIGN_UP, GF_SECURITY_*.
- **guacamole** – TZ (optional); POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD (required; strong password shared by Postgres and the Guacamole web app). No host ports; access via Caddy only.
- **headscale** – TZ (optional). Config via `HEADSCALE_CONFIG_B64` (base64-encoded config.yaml); see stack README.
- **holehe** – TZ (optional). OSINT web UI; optional env. No host ports; access via Caddy only. See stack README.
- **immich** – TZ, LANG, LC_ALL, LC_CTYPE (server); plus DB_PASSWORD, DB_*, optional IMMICH_CONFIG_FILE.
- **infisical** – TZ, LANG, LC_ALL, LC_CTYPE (backend); ENCRYPTION_KEY, AUTH_SECRET, POSTGRES_*, DB_CONNECTION_URI, REDIS_URL, SITE_URL; optional SMTP_*, OAuth CLIENT_* (see stack `stack.env.example`).
- **it-tools** – TZ, LANG, LC_ALL, LC_CTYPE.
- **jellyfin** – TZ; PUID, PGID. Media libraries use `/data/tv`, `/data/movies`, `/data/music`; configure libraries in the Jellyfin UI.
- **komga** – TZ (optional); SERVER_PORT=25600. Optional JAVA_TOOL_OPTIONS (e.g. `-Xmx4g` for large libraries). No host ports; access via Caddy to komga:25600. First user created in web UI; libraries point at `/data` or bind-mount. Image does not use PUID/PGID; for bind-mounted libraries ensure the host directory is owned by the container user (e.g. `chown -R 1000:1000 /path/to/comics`). See [Komga configuration](https://komga.org/docs/installation/configuration) and stack README.
- **kavita** – TZ (optional); PUID, PGID (optional). LinuxServer image; `/config`, `/data` (libraries). No host ports; access via Caddy to kavita:5000. Setup wizard on first run; add libraries in UI. See [LinuxServer Kavita](https://docs.linuxserver.io/images/docker-kavita) and stack README.
- **librechat** – TZ, LANG, LC_ALL, LC_CTYPE; LIBRECHAT_HOST_PORT, MONGODB_*, REDIS_*; MONGO_INITDB_ROOT_USERNAME, MONGO_INITDB_ROOT_PASSWORD, REDIS_PASSWORD; DOMAIN_CLIENT, DOMAIN_SERVER; OLLAMA_BASE_URL; optional OPENAI_API_KEY; JWT_SECRET, JWT_REFRESH_SECRET (required for production; generate with `openssl rand -base64 32`); ALLOW_REGISTRATION, ALLOW_SOCIAL_LOGIN. See stack `stack.env.example`.
- **lidarr** – TZ; PUID, PGID. Uses `/music`, `/downloads`, `/torrents` inside the container; wire to NZBGet/qBittorrent and Prowlarr/NZBHydra 2.
- **linkstack** – TZ (optional); optional SERVER_ADMIN, HTTP_SERVER_NAME, HTTPS_SERVER_NAME, LOG_LEVEL, PHP_MEMORY_LIMIT, UPLOAD_MAX_FILESIZE (see stack `stack.env.example`).
- **lanraragi** – TZ (optional); LRR_UID, LRR_GID (optional, default 9001); LRR_AUTOFIX_PERMISSIONS (optional, set to -1 to skip). difegue/lanraragi image; content at `/home/koyomi/lanraragi/content`, database and thumb volumes. No host ports; access via Caddy to lanraragi:3000. See [Lanraragi Docker](https://sugoi.gitbook.io/lanraragi/installing-lanraragi/docker) and stack README.
- **linkwarden** – TZ (optional); NEXTAUTH_SECRET, POSTGRES_PASSWORD, MEILI_MASTER_KEY, NEXTAUTH_URL (when behind reverse proxy).
- **maigret** – TZ (optional). No host ports; web UI on port 5000, access via Caddy only. Reports in named volume `maigret-reports`. See stack README.
- **mealie** – TZ, LANG, LC_ALL, LC_CTYPE; BASE_URL (when behind reverse proxy), ALLOW_SIGNUP; optional DB_ENGINE (sqlite/postgres).
- **metagoofil** – TZ (optional). OSINT CLI; optional env for output. See stack README.
- **metube** – TZ (optional); PUID, PGID, UMASK (optional). yt-dlp web GUI; downloads to named volume. See stack `stack.env.example`.
- **mylar3** – TZ (optional); PUID, PGID (optional). LinuxServer image; `/config`, `/comics`, `/downloads`. No host ports; access via Caddy to mylar3:8090. Uses `usenet` and `torrents` networks; configure NZBGet (e.g. nzbget:6789), qBittorrent (e.g. qbittorrent:8080), Prowlarr in the UI. See [LinuxServer Mylar3](https://docs.linuxserver.io/images/docker-mylar3) and stack README.
- **naisho** – TZ (optional); SECRET_KEY_BASE (required; e.g. `openssl rand -hex 64`); optional RAILS_LOG_LEVEL. Builds from GitHub; no host ports; access via Caddy only. SMTP configured in-app when sending deletion emails. See stack `stack.env.example` and README.
- **navidrome** – TZ (optional); ND_BASEURL (optional but recommended when behind Caddy; set to your full Navidrome URL, e.g. `https://music.yourdomain.com`); ND_LOGLEVEL, ND_SCANSCHEDULE, ND_SESSIONTIMEOUT and other `ND_` options for tuning behaviour. Image does not use PUID/PGID; for bind-mounted `/music` ensure host path is readable by the container (e.g. `chown -R 1000:1000 /path`). See stack `stack.env.example` and [Navidrome configuration options](https://navidrome.org/docs/usage/configuration/options/).
- **nodered** – TZ, LANG, LC_ALL, LC_CTYPE (optional). Flow editor; no host ports; access via Caddy only. See stack README.
- **nzbget** – TZ (optional); PUID, PGID, optional UMASK. Optional NZBGET_USER and NZBGET_PASS for the web UI. Usenet servers and categories are configured in the NZBGet UI.
- **nzbhydra2** – TZ (optional); PUID, PGID, optional UMASK. API key and indexer configuration are set in the NZBHydra 2 UI.
- **n8n** – TZ, LANG, LC_ALL, LC_CTYPE; N8N_HOST, WEBHOOK_URL (required when behind Caddy; set to your base URL e.g. https://n8n.home or https://n8n.yourdomain.com); N8N_PORT=5678, N8N_PROTOCOL=https; optional N8N_ENCRYPTION_KEY (e.g. `openssl rand -hex 32`). No host ports; access via Caddy only. See stack `stack.env.example`.
- **ollama** – TZ, LANG, LC_ALL, LC_CTYPE; OLLAMA_HOST_PORT; OLLAMA_MODELS_PATH (path for models; use absolute path for large storage). Other data uses Docker volume `ollama_data`. GPU: requires NVIDIA Container Toolkit; no API keys.
- **onionprobe** – Optional: GRAFANA_DATABASE_PASSWORD, GF_SERVER_ROOT_URL (e.g. https://onionprobe.home), PROMETHEUS_WEB_EXTERNAL_URL; requires upstream repo cloned into `./repo` (run `./clone-repo.sh`). No host ports; access via Caddy to op-grafana:3000. See stack README.
- **onionscan** – CLI only; no web server or ports. Optional TZ. Container runs Tor; run scans via `docker compose exec onionscan onionscan [options] <onion-address>`. See stack README.
- **open-notebook** – TZ, LANG, LC_ALL, LC_CTYPE; OPEN_NOTEBOOK_ENCRYPTION_KEY (required; generate with `openssl rand -base64 32`); SURREAL_USER, SURREAL_PASSWORD, SURREAL_NAMESPACE, SURREAL_DATABASE; OLLAMA_BASE_URL (optional; e.g. http://ollama:11434 or http://host.docker.internal:11434). See stack `stack.env.example`.
- **open-webui** – TZ, LANG, LC_ALL, LC_CTYPE; OPEN_WEBUI_HOST_PORT; OLLAMA_BASE_URL (required for Ollama; e.g. http://ollama:11434 or http://host.docker.internal:11434); optional OPENAI_API_KEY, ENABLE_SIGNUP, DEFAULT_USER_ROLE, WEBUI_SECRET_KEY, WEBUI_JWT_SECRET_KEY. See stack `stack.env.example`.
- **paperless-ngx** – TZ (webserver); plus app-specific (PAPERLESS_URL, PAPERLESS_SECRET_KEY, etc.).
- **password-pusher** – TZ (optional); PWPUSH_MASTER_KEY (required); optional PWP__HOST_DOMAIN, PWP__HOST_PROTOCOL when behind Caddy; PWP__ENABLE_LOGINS, PWP__PURGE_AFTER (see stack `stack.env.example`).
- **perplexica** – TZ, LANG, LC_ALL, LC_CTYPE; PERPLEXICA_HOST_PORT, PERPLEXICA_DATA_PATH; optional SEARXNG_API_URL (leave empty for bundled SearxNG), OLLAMA_BASE_URL. See stack `stack.env.example`.
- **phoneinfoga** – TZ (optional). OSINT web UI/API for phone recon; optional env. No host ports; access via Caddy only. See stack README.
- **plex** – TZ; PUID, PGID; VERSION (usually `docker`); optional PLEX_CLAIM (one-time claim token to link the server to your Plex account). Libraries use `/data/tv`, `/data/movies`, `/data/music`.
- **plaso** – TZ (optional). CLI only; digital forensics timeline (log2timeline, psort). Mount evidence to `/data`; run via `docker compose run --rm plaso log2timeline ...` or `psort ...`. See stack README.
- **portainer** – (Portainer CE; add TZ/LANG if you ever customize it.)
- **postfix** – Same as **smtp-relay** (stack folder `postfix`). TZ (optional); ALLOWED_SENDER_DOMAINS (recommended); RELAYHOST (required), RELAYHOST_USERNAME, RELAYHOST_PASSWORD. See stack `stack.env.example` and [boky/postfix docs](https://github.com/bokysan/docker-postfix).
- **privotron** – CLI only; no web server or ports. Optional TZ; PRIVOTRON_VERSION (build arg, default main). Profiles in volume `privotron-profiles`. Run: `docker compose run --rm privotron --profile NAME` or with inline args. See stack README.
- **prometheus** – TZ, LANG, LC_ALL, LC_CTYPE; config via prometheus.yml (no env secrets).
- **prowlarr** – TZ; PUID, PGID. Manages Usenet and torrent indexers and syncs them to Sonarr/Radarr/Lidarr/Readarr.
- **qbittorrent** – TZ; PUID, PGID (LinuxServer qBittorrent). Gluetun VPN: VPN_SERVICE_PROVIDER, VPN_TYPE, and provider-specific vars (e.g. WIREGUARD_PRIVATE_KEY, WIREGUARD_ADDRESSES for custom WireGuard). Uses `torrents` network and `torrents_downloads` volume; reachable as `qbittorrent:8080` for *arr. See stack `stack.env.example` and [Gluetun configuration](https://gluetun.com/configuration/).
- **radarr** – TZ; PUID, PGID. Uses `/movies`, `/downloads`, `/torrents` inside the container; wire to NZBGet/qBittorrent and Prowlarr/NZBHydra 2.
- **readarr** – TZ; PUID, PGID. Uses `/books`, `/downloads`, `/torrents` inside the container; wire to NZBGet/qBittorrent and Prowlarr/NZBHydra 2.
- **reconftw** – TZ (optional). Recon framework CLI; optional env. See stack README.
- **romm** – TZ (optional); ROMM_AUTH_SECRET_KEY (required; e.g. `openssl rand -hex 32`); ROMM_BASE_URL (required when behind Caddy; e.g. https://romm.yourdomain.com); MARIADB_ROOT_PASSWORD, MARIADB_PASSWORD, MARIADB_DATABASE, MARIADB_USER for MariaDB. Config via `config.yml` in config volume or bind-mount. No host ports; access via Caddy to romm:8080. Optional metadata API keys: IGDB_*, SCREENSCRAPER_*, MOBYGAMES_API_KEY, STEAMGRIDDB_API_KEY, RETROACHIEVEMENTS_API_KEY. See [RomM env docs](https://docs.romm.app/latest/Getting-Started/Environment-Variables/) and stack README.
- **rtorrent-flood** – TZ; PUID, PGID, optional UMASK. Uses `/downloads` inside the container; configure Flood and rTorrent via the web UI.
- **searx-ng** – TZ, LANG, LC_ALL, LC_CTYPE (searxng); plus SEARXNG_SECRET, SEARXNG_BASE_URL.
- **simplelogin** – TZ (optional); URL (required; e.g. https://simplelogin.home); EMAIL_DOMAIN, EMAIL_SERVERS_WITH_PRIORITY, SUPPORT_EMAIL; FLASK_SECRET (required; e.g. `openssl rand -hex 32`); POSTGRES_PASSWORD, POSTGRES_USER, POSTGRES_DB; DKIM key at `./data/dkim.key`; optional POSTFIX_SERVER, POSTFIX_PORT for outbound SMTP; DISABLE_REGISTRATION. No host ports; access via Caddy only. See stack `stack.env.example` and README.
- **slink** – TZ (optional); ORIGIN (required; must match Caddy hostname, e.g. https://slink.home); USER_APPROVAL_REQUIRED, IMAGE_MAX_SIZE, STORAGE_PROVIDER (local/smb/s3). Image does not use PUID/PGID; for bind-mounted storage ensure host path is owned by the container user (e.g. `chown -R 1000:1000 /path`). See stack `stack.env.example` and [Slink docs](https://docs.slinkapp.io).
- **smtp-relay** – TZ (optional); ALLOWED_SENDER_DOMAINS (recommended); RELAYHOST (required), RELAYHOST_USERNAME, RELAYHOST_PASSWORD; optional POSTFIX_myhostname, POSTFIX_message_size_limit. See stack `stack.env.example` and [boky/postfix docs](https://github.com/bokysan/docker-postfix).
- **social-hunt** – TZ (optional); ADMIN_TOKEN (required; dashboard login; e.g. `openssl rand -hex 32`); SOCIAL_HUNT_PUBLIC_URL (required when behind Caddy; e.g. https://social-hunt.home); optional SOCIAL_HUNT_ENABLE_TOKEN_BOOTSTRAP, SOCIAL_HUNT_ENABLE_WEB_PLUGIN_UPLOAD, SOCIAL_HUNT_PROXY, SOCIAL_HUNT_CLEARNET_PROXY, HCAPTCHA_*. API keys (HIBP, Snusbase, etc.) via dashboard Settings. No host ports; access via Caddy only. See stack `stack.env.example` and README.
- **spiderfoot** – TZ (optional). OSINT scanner web UI; optional env. No host ports; access via Caddy only. See stack README.
- **stoat** – Uses upstream generator; `.env.web` holds `HOSTNAME`, `REVOLT_PUBLIC_URL`, `VITE_*` URLs; `Revolt.toml` controls hosts, LiveKit, push keys, files encryption. Internal services use no host ports; main Caddy reverse-proxies to `stoat-caddy:80`. See upstream Stoat docs and stack README for options (invite-only, captcha, email, S3, mobile push).
- **sublist3r** – TZ (optional). Subdomain enumeration CLI; optional env for output. See stack README.
- **theharvester** – TZ (optional). OSINT recon API; optional env. No host ports; access via Caddy only. See stack README.
- **threat-dragon** – TZ (optional); SESSION_SIGNING_KEY (required; 32-char hex); optional GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET (or Bitbucket/GitLab) for repo storage. .env mounted read-only. No host ports; access via Caddy to threatdragon:3000.
- **torbot** – TZ (optional). CLI only (OWASP TorBot). Tor in separate container (tor:9050); run crawls via `docker compose exec torbot torbot -u <url> --host tor --port 9050 [options]`. See stack README.
- **uptime-kuma** – TZ, LANG, LC_ALL, LC_CTYPE.
- **vaultwarden** – TZ; DOMAIN (when behind reverse proxy), SIGNUPS_ALLOWED; optional ADMIN_TOKEN, WEBSOCKET_ENABLED.
- **wireguard** – TZ; PUID, PGID (LinuxServer); SERVERURL (public IP or DNS, or `auto`), SERVERPORT (51820), PEERS; optional PEERDNS, INTERNAL_SUBNET, ALLOWEDIPS, PERSISTENTKEEPALIVE_PEERS. UDP 51820 on host; no Caddy. See [LinuxServer WireGuard docs](https://docs.linuxserver.io/images/docker-wireguard) and stack `stack.env.example`.
- **watchtower** – TZ, LANG, LC_ALL, LC_CTYPE.
- **web-check** – TZ, LANG, LC_ALL, LC_CTYPE; optional API keys in README / `stack.env.example`.
- **yourls** – TZ (optional); YOURLS_SITE (required, must match Caddy hostname); YOURLS_USER, YOURLS_PASS, YOURLS_COOKIEKEY; YOURLS_DB_PASSWORD, YOURLS_DB_ROOT_PASSWORD; optional YOURLS_DB_NAME, YOURLS_DB_USER (see stack `stack.env.example`).
- **zap** – TZ (optional). No host ports; access via Caddy to zap:8090. OWASP ZAP daemon + web UI for web/API security scanning.
