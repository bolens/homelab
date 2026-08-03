# Environment variables — Docker homelab stacks

Use this as a reference when adding new stacks. Per-stack environment variable
details live in each stack's `README.md` under the **Environment variables**
section. This file covers shared conventions and common variables only.

---

## Shared env file (TZ & locale)

To set `TZ` and locale in one place for all stacks, see
[SHARED-RESOURCES.md – Shared env file](SHARED-RESOURCES.md#1-shared-env-file-tz--locale).

New and updated stacks should **not** duplicate `TZ`, `LANG`, `LC_ALL`, or
`LC_CTYPE` in their own `stack.env.example` — prefer `../../shared.env` with a
short comment pointing to SHARED-RESOURCES.md.

```env
# Typical contents of shared.env (do not commit real values)
TZ=America/Denver
LANG=en_US.UTF-8
LC_ALL=en_US.UTF-8
LC_CTYPE=en_US.UTF-8
```

- **TZ** – Logs and in-app times. Set to your IANA timezone (e.g. `America/Denver`, `Europe/London`).
- **LANG / LC_ALL** – Default locale and encoding (UTF-8). Usually provided via `shared.env` rather than per-stack.
- **LC_CTYPE** – Character classification (UTF-8); some apps use it for filenames and text. Usually provided via `shared.env` rather than per-stack.

---

## Common per-app variables (checklist)

Not every image respects all of these. Check the upstream image docs.

- **LANGUAGE** – Message language, e.g. `en_US:en` (if the image shows translated messages).
- **PYTHONIOENCODING** – For Python apps: `UTF-8` so stdin/stdout/stderr are UTF-8.
- **NODE_OPTIONS** – For Node apps, e.g. `--max-old-space-size=512` if you need to cap memory.
- **PUID / PGID** – Some images (e.g. LinuxServer.io) use these to run as a specific user; set to your host user if you want file ownership to match.
- **UMASK** – e.g. `0022` or `0002` if the image documents it for volume file permissions.

---

## Secret generation patterns

These patterns appear across many stacks:

```bash
# 32-byte base64 secret (Laravel APP_KEY, general secrets)
openssl rand -base64 32

# 32-byte hex secret (general, JWT, Flask)
openssl rand -hex 32

# 64-byte hex secret (Rails SECRET_KEY_BASE, Docuseal SECRET_KEY_BASE)
openssl rand -hex 64

# Laravel APP_KEY via artisan (Firefly III, Snipe-IT, etc.)
docker run --rm <image> php artisan key:generate --show
```

---

## Per-stack environment variables

Each stack's `README.md` documents its required and optional environment
variables. See the stack directory for `stack.env.example` as the authoritative
list of variables to set.

Quick reference — find a stack:

| Stack | Notes |
|-------|-------|
| acquire | CLI only; forensic artifact collection. |
| actual-budget | TZ only; sync server for Actual Budget desktop/mobile app. |
| adguard-home | DNS on host 53/853; no stack-specific env required. |
| affine | Optional AFFINE_SERVER_EXTERNAL_URL; no host ports. |
| afl-libfuzzer | CLI only; fuzzing toolkit. |
| ail / ail-framework | TZ only; Analysis Information Leak framework. Resource-heavy (>6 GB RAM). |
| alertmanager | Config file-based; see ALERTMANAGER_CONFIG_PATH. |
| anything-llm | JWT_SECRET required; LLM/Ollama vars; SYS_ADMIN cap per upstream. |
| appflowy | Scaffold; configure URL settings in stack.env. |
| archisteamfarm | ASF_UID optional; config/ASF.json (Kestrel + IPCPassword). |
| archivebox | ADMIN_USERNAME/PASSWORD, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS. |
| asking / asking-ng | JWT_SECRET, ADMIN_TOKEN, DATABASE_URI; VITE_* are build-time args. |
| atomic-red-team | CLI only; attack simulation. |
| audiobookshelf | TZ only; image does not use PUID/PGID. |
| auth-fuzz | CLI only; auth fuzzing toolkit. |
| baserow | BASEROW_PUBLIC_URL required behind Caddy. |
| bazarr | TZ, PUID, PGID; BAZARR_TV_PATH, BAZARR_MOVIES_PATH → /tv, /movies. |
| beszel | BESZEL_APP_URL required; BESZEL_DATA_DIR optional. |
| blackbird | CLI only; OSINT. |
| blackbox-exporter | Config file-based; Prometheus scrapes :9115. |
| bookstack | APP_URL required; MYSQL_ROOT_PASSWORD, MYSQL_PASSWORD. |
| caddy | TZ/locale via shared.env only. |
| cadvisor | TZ/locale via shared.env only. |
| calcom | DATABASE_URL, CAL_SIGNATURE_TOKEN required; REDIS_URL. |
| calibre-web | PUID/PGID; optional SECRET_KEY, DOCKER_MODS. |
| cloudflare-tunnel | TZ/locale via shared.env only. |
| code-server | PUID, PGID, PASSWORD required; PROXY_DOMAIN. |
| convertx | JWT_SECRET recommended; ACCOUNT_REGISTRATION. |
| cowrie | Honeypot; no web UI; logs via Loki/Promtail. |
| crowdsec | GID, COLLECTIONS; config via acquisitions file. |
| cryptpad | CPAD_MAIN_DOMAIN optional; shared.env for locale. |
| cups | CUPSADMIN, CUPSPASSWORD required; named volume for /etc/cups. |
| databasus | See stack README and stack.env.example. |
| dbgate | See stack README and stack.env.example. |
| ddns-updater | Config via ./data/config.json; optional SHOUTRRR_ADDRESSES for notifications. |
| dependency-track | API_BASE_URL required; POSTGRES_PASSWORD. |
| dionaea-conpot | Honeypot; CLI/daemon only. |
| dispatcharr | Placeholder; compose not yet created. |
| diun | DIUN_WATCH_*, DIUN_PROVIDERS_DOCKER, DIUN_NOTIF_*. |
| docker-forensics-toolkit | CLI only; optional DOF_IMAGE_MOUNTPOINT. |
| docker-gc | DRY_RUN, EXCLUDE_IMAGES, EXCLUDE_CONTAINERS. |
| docuseal | POSTGRES_PASSWORD, DATABASE_URL, SECRET_KEY_BASE required. |
| dozzle | DOZZLE_CONFIG_DIR; optional DOZZLE_AUTH_PROVIDER. |
| emby | TZ, PUID, PGID; EMBY_TV_PATH, EMBY_MOVIES_PATH, EMBY_MUSIC_PATH → /data/... |
| enclosed | PUBLIC_BASE_API_URL behind proxy; optional AUTHENTICATION_JWT_SECRET. |
| ersatztv | TZ only; IPTV server on :8409. |
| explo | Scheduled playlist jobs; ListenBrainz; Ollama target system vars. |
| firefly-iii | DB_*, APP_URL, APP_KEY (artisan generate) required. |
| flaresolverr | LOG_LEVEL; optional PROXY_URL; accessible at flaresolverr:8191. |
| freshrss | TZ, PUID, PGID optional. |
| ghunt | CLI only; OSINT for Google accounts. |
| gitea | GITEA_DB_*, GITEA_ROOT_URL required. |
| gitlab | Placeholder; configure GITLAB_OMNIBUS_CONFIG per upstream. |
| gitlab-runners | Placeholder; REGISTRATION_TOKEN, CI_SERVER_URL required. |
| glance | Config file-based (./config); no env required. |
| gluetun | VPN_SERVICE_PROVIDER, VPN_TYPE + provider-specific vars. |
| gotenberg | Placeholder; stateless PDF service; no env required for basic use. |
| grafana | GF_SERVER_ROOT_URL optional; GF_SECURITY_* optional. |
| grafana-alloy | ALLOY_CONFIG_PATH required (Portainer). |
| guacamole | POSTGRES_DB/USER/PASSWORD required. |
| handbrake | USER_ID, GROUP_ID, UMASK for file ownership; placeholder stack. |
| harbor | Deployed via upstream installer (harbor.yml), not a standard compose stack. |
| hashcat | No env required; CLI only; optional HASHCAT_WORDLIST_DIR. |
| headscale | HEADSCALE_CONFIG_B64 (base64-encoded config.yaml). |
| hedgedoc | POSTGRES_DB/USER/PASSWORD, CMD_DOMAIN required. |
| holehe | OSINT web UI; no env required. |
| home-assistant | TZ/locale via shared.env; Zigbee2MQTT + Mosquitto optional. |
| homarr | TZ only; dashboard on :7575. |
| homepage | TZ only; static landing page. |
| immich | DB_PASSWORD, DB_* required; shared.env for locale. |
| infisical | ENCRYPTION_KEY, AUTH_SECRET, POSTGRES_*, REDIS_URL, SITE_URL required. |
| influxdb | Placeholder; INFLUXDB_ADMIN_USER/PASSWORD per upstream. |
| it-tools | TZ/locale via shared.env only. |
| jellyfin | TZ, PUID, PGID; JELLYFIN_TV_PATH, JELLYFIN_MOVIES_PATH, JELLYFIN_MUSIC_PATH. |
| jellystat | POSTGRES_*, JWT_SECRET required; optional JS_BASE_URL. |
| joplin-server | POSTGRES_*, APP_BASE_URL required. |
| kali | KALI_PASSWORD for VNC/RDP; offensive security toolkit. |
| kasm | KASM_PORT; privileged mode; set Proxy Port to 0 after install. |
| kavita | TZ, PUID, PGID optional; LinuxServer image. |
| keycloak | POSTGRES_*, KEYCLOAK_ADMIN/PASSWORD, KC_HOSTNAME required. |
| kokoro-tts | KOKORO_IMAGE_TAG optional; API_LOG_LEVEL optional. |
| kometa | KOMETA_CONFIG_PATH, KOMETA_DATA_PATH required; batch runner. |
| komga | SERVER_PORT=25600; optional JAVA_TOOL_OPTIONS for large libraries. |
| lanraragi | LRR_UID/GID optional; content at /home/koyomi/lanraragi/content. |
| librechat | MONGO_INITDB_*, REDIS_PASSWORD, DOMAIN_*, JWT_SECRET required. |
| lidarr | TZ, PUID, PGID; LIDARR_MEDIA_PATH → /data. |
| linkding | TZ optional; optional LD_DISABLE_BACKGROUND_TASKS. |
| linkstack | Optional SERVER_ADMIN, HTTP_SERVER_NAME, PHP_MEMORY_LIMIT. |
| linkwarden | NEXTAUTH_SECRET, POSTGRES_PASSWORD, MEILI_MASTER_KEY required. |
| litellm | LITELLM_MASTER_KEY, UI_USERNAME/PASSWORD, POSTGRES_PASSWORD required. |
| logseq-sync | Experimental; optional TZ; run ./clone-repo.sh first. |
| loki | Config file-based; Grafana data source at http://loki:3100. |
| maigret | OSINT; no env required; reports in named volume. |
| mailpit | No env required; SMTP on :1025, web on :8025. |
| maloja | MALOJA_FORCE_PASSWORD required on first start; optional API keys. |
| matomo | MATOMO_DB_NAME/USER/PASSWORD required; optional MATOMO_BASE_URL. |
| mattermost | POSTGRES_*, MM_SERVICESETTINGS_SITEURL required. |
| mealie | BASE_URL behind proxy; ALLOW_SIGNUP; optional DB_ENGINE. |
| meilisearch | MEILI_MASTER_KEY recommended; MEILI_ENV. |
| metagoofil | CLI only; OSINT. |
| metube | TZ, PUID, PGID, UMASK optional. |
| minio | MINIO_ROOT_USER, MINIO_ROOT_PASSWORD required. |
| mosquitto | Config via mosquitto.conf; MQTT on :1883. |
| mylar3 | TZ, PUID, PGID; MYLAR3_MEDIA_PATH → /data. |
| n8n | N8N_HOST, WEBHOOK_URL required behind Caddy; N8N_ENCRYPTION_KEY recommended. |
| naisho | SECRET_KEY_BASE required (openssl rand -hex 64). |
| navidrome | ND_BASEURL recommended; ND_SCANSCHEDULE, ND_LOGLEVEL. |
| netbird | NETBIRD_MGMT_API_ENDPOINT, AUTH_* vars; UDP 3478 for STUN. |
| netboot.xyz | Placeholder; TFTP/HTTP netboot server; UDP 69 + HTTP on host. |
| netbox | Pointer stack; use upstream netbox-docker. |
| netexec | CLI only; network pentesting (crackmapexec successor). |
| nextcloud | POSTGRES_*, NEXTCLOUD_TRUSTED_DOMAINS, NEXTCLOUD_ADMIN_* required. |
| node-exporter | No env; Prometheus scrapes :9100; host filesystem read-only. |
| node-red | TZ/locale via shared.env; flow editor. |
| nodepad | OLLAMA_ORIGIN, NODEPAD_SITE_URL, UMAMI_* required at runtime. |
| ntfy | NTFY_BASE_URL recommended behind Caddy. |
| ntopng | TZ/locale via shared.env; host networking; web on :3000. |
| nut-server | NUT_CONFIG_DIR required (path to ups.conf, upsd.*, upsmon.conf). |
| nzbget | PUID, PGID optional; NZBGET_DOWNLOADS_PATH → /downloads; servers and categories in UI. |
| nzbhydra2 | PUID, PGID optional; config in UI. |
| oasis | No env required; TZ from shared.env. |
| ollama | OLLAMA_HOST_PORT, OLLAMA_MODELS_PATH; GPU deploy block optional. |
| ombi | Placeholder; Plex/Jellyfin URL + API token configured in UI. |
| onionprobe | GRAFANA_DATABASE_PASSWORD optional; upstream repo required (./clone-repo.sh). |
| onionscan | CLI only; Tor container required. |
| open-notebook | API_URL, OPEN_NOTEBOOK_ENCRYPTION_KEY, SURREAL_* required. |
| open-webui | OLLAMA_BASE_URL required; optional OPENAI_API_KEY, WEBUI_SECRET_KEY. |
| opengist | See stack README and stack.env.example. |
| openspeedtest | No env required; speed test server. |
| outline | POSTGRES_*, URL, SECRET_KEY, UTILS_SECRET, AWS_* (MinIO) required. |
| paperless-ai-next | Paperless-ngx API URL/token + Ollama vars required. |
| paperless-gpt | PAPERLESS_*, OLLAMA_HOST required. |
| paperless-ngx | PAPERLESS_URL, PAPERLESS_SECRET_KEY, plus DB and broker vars. |
| password-pusher | PWPUSH_MASTER_KEY required; optional PWP__HOST_DOMAIN, PWP__ENABLE_LOGINS. |
| peanut | See stack README and stack.env.example. |
| perplexica | SEARXNG_API_URL, OLLAMA_BASE_URL optional; secrets configured in UI. |
| pgadmin | See stack README and stack.env.example. |
| phoneinfoga | OSINT; no env required. |
| picard | PUID, PGID optional; PICARD_MEDIA_PATH → /data. |
| pihole | See stack README; DNS port 53 conflict resolution required on host. |
| plaso | CLI only; digital forensics (log2timeline/psort). |
| plex | TZ, PUID, PGID, VERSION, PLEX_*_PATH, optional PLEX_CLAIM. |
| pocketbase | See stack README and stack.env.example. |
| postfix / smtp-relay | ALLOWED_SENDER_DOMAINS, RELAYHOST required; RELAYHOST_USERNAME/PASSWORD. |
| posthog | DOMAIN, POSTHOG_APP_TAG required; auto-fill secrets via ./prepare-stack.sh. |
| postiz | See stack README and stack.env.example. |
| presidio | See stack README and stack.env.example. |
| privatebin | See stack README; config file-based. |
| privotron | CLI only; PRIVOTRON_VERSION build arg. |
| prometheus | Config file-based (prometheus.yml); no env secrets. |
| promtail | Config file-based (promtail-config.yml); ships logs to Loki. |
| prowlarr | TZ, PUID, PGID; indexer manager. |
| pwntools-gdb | CLI only; exploit dev toolkit. |
| qbittorrent | TZ, PUID, PGID; Gluetun VPN_* vars if using VPN. |
| rackula | See stack README and stack.env.example. |
| radarr | TZ, PUID, PGID; RADARR_MEDIA_PATH → /data. |
| readarr | TZ, PUID, PGID; READARR_MEDIA_PATH → /data. |
| reconftw | CLI only; recon framework. |
| resilio | See stack README and stack.env.example. |
| responder-mitm6 | See stack README; network attack toolkit. |
| restic | RESTIC_REPOSITORY, RESTIC_PASSWORD, AWS_* required; BACKUP_CRON. |
| romm | ROMM_AUTH_SECRET_KEY, ROMM_BASE_URL, MARIADB_* required; optional metadata API keys. |
| rtorrent-flood | TZ, PUID, PGID, UMASK optional. |
| rustdesk | See stack README; host networking for TURN/STUN. |
| rustfs | See stack README and stack.env.example. |
| scrypted | See stack README; hardware acceleration config in UI. |
| scrutiny | TZ optional; adjust devices/volumes in compose for your disks. |
| seafile | TIME_ZONE, MYSQL_ROOT_PASSWORD, SEAFILE_DB_*, SEAFILE_SERVER_HOSTNAME required. |
| searx-ng | SEARXNG_SECRET, SEARXNG_BASE_URL required; config via settings.yml. |
| seerr | See stack README and stack.env.example. |
| shlink | DEFAULT_DOMAIN, GEOLITE_LICENSE_KEY required; IS_HTTPS_ENABLED=true behind Caddy. |
| simplelogin | URL, EMAIL_DOMAIN, FLASK_SECRET, POSTGRES_* required; DKIM key at ./data/dkim.key. |
| slink | ORIGIN required (must match Caddy hostname); STORAGE_PROVIDER. |
| snipe-it | APP_URL, APP_KEY (artisan generate), DB_*, MYSQL_* required. |
| snowflake-relay | See stack README and stack.env.example. |
| social-hunt | ADMIN_TOKEN, SOCIAL_HUNT_PUBLIC_URL required. |
| sonarr | TZ, PUID, PGID; SONARR_MEDIA_PATH → /data. |
| soulseek | SLSKD_SLSK_USERNAME/PASSWORD required; SLSKD_SLSK_LISTEN_PORT (50300). |
| spiderfoot | OSINT scanner; no env required. |
| stirling-pdf | TZ optional; PDF tools. |
| stoat | .env.web (HOSTNAME, REVOLT_PUBLIC_URL, VITE_*); Revolt.toml for service config. |
| sublist3r | CLI only; subdomain enumeration. |
| super-productivity | TZ/locale via shared.env; browser-based productivity UI. |
| syncthing | TZ optional. |
| tailscale-exporter | See stack README; TAILSCALE_API_KEY and TAILNET required. |
| tautulli | See stack README; TZ and Plex server connection configured in UI. |
| terminus | Multi-service stack; see stack README for service-specific env. |
| theharvester | OSINT; no env required. |
| thelounge | THELOUNGE_PUBLIC optional; port 9000. |
| threat-dragon | SESSION_SIGNING_KEY required (32-char hex); optional OAuth vars. |
| tika | Apache Tika REST API; TZ only. |
| torbot | CLI only; OWASP TorBot; Tor on :9050. |
| trilium | TZ/locale via shared.env; optional TRILIUM_PORT. |
| twitch-drops-miner | See stack README and stack.env.example. |
| umami | POSTGRES_PASSWORD, APP_SECRET required; ./prepare-stack.sh copies to .env. |
| unbound | See stack README; recursive DNS resolver. |
| uptime-kuma | TZ/locale via shared.env only. |
| vaultwarden | TZ, DOMAIN, SIGNUPS_ALLOWED; optional ADMIN_TOKEN, WEBSOCKET_ENABLED. |
| vector | Config via vector.toml; ships logs to Loki. |
| vikunja | VIKUNJA_SERVICE_PUBLICURL (with trailing slash), VIKUNJA_DATABASE_TYPE required. |
| watchtower | TZ/locale via shared.env; WATCHTOWER_NOTIFICATION_URL via stack.env. |
| web-check | TZ/locale via shared.env; optional API keys in stack.env.example. |
| whisparr | PUID, PGID; WHISPARR_*_PATH bind-mount vars required. |
| whisper-asr | ASR_ENGINE, ASR_MODEL, ASR_DEVICE required; GPU image for CUDA. |
| wireguard | SERVERURL, SERVERPORT, PEERS required; PUID, PGID. |
| woodpecker-ci | POSTGRES_*, WOODPECKER_AGENT_SECRET, Gitea OAuth vars required. |
| yourls | YOURLS_SITE, YOURLS_USER, YOURLS_PASS, YOURLS_COOKIEKEY, DB vars required. |
| zed-attack-proxy | TZ optional; Webswing UI on :8080; proxy on :8080 for browser/tool config. |
| zigbee2mqtt | ZIGBEE2MQTT_CONFIG_MQTT_SERVER required; Mosquitto on monitor network. |
