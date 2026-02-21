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

- **audiobookshelf** – TZ (optional).
- **caddy** – TZ, LANG, LC_ALL, LC_CTYPE.
- **cloudflare-tunnel** – TZ, LANG, LC_ALL, LC_CTYPE.
- **freshrss** – TZ, PUID, PGID (optional).
- **headscale** – TZ (optional). Config via `HEADSCALE_CONFIG_B64` (base64-encoded config.yaml); see stack README.
- **immich** – TZ, LANG, LC_ALL, LC_CTYPE (server); plus DB_PASSWORD, DB_*, optional IMMICH_CONFIG_FILE.
- **it-tools** – TZ, LANG, LC_ALL, LC_CTYPE.
- **linkwarden** – TZ (optional); NEXTAUTH_SECRET, POSTGRES_PASSWORD, MEILI_MASTER_KEY, NEXTAUTH_URL (when behind reverse proxy).
- **mealie** – TZ, LANG, LC_ALL, LC_CTYPE; BASE_URL (when behind reverse proxy), ALLOW_SIGNUP; optional DB_ENGINE (sqlite/postgres).
- **paperless-ngx** – TZ (webserver); plus app-specific (PAPERLESS_URL, PAPERLESS_SECRET_KEY, etc.).
- **portainer** – (Portainer CE; add TZ/LANG if you ever customize it.)
- **searx-ng** – TZ, LANG, LC_ALL, LC_CTYPE (searxng); plus SEARXNG_SECRET, SEARXNG_BASE_URL.
- **uptime-kuma** – TZ, LANG, LC_ALL, LC_CTYPE.
- **vaultwarden** – TZ; DOMAIN (when behind reverse proxy), SIGNUPS_ALLOWED; optional ADMIN_TOKEN, WEBSOCKET_ENABLED.
- **watchtower** – TZ, LANG, LC_ALL, LC_CTYPE.
- **web-check** – TZ, LANG, LC_ALL, LC_CTYPE; optional API keys in README / .env.example.
- **dozzle** – TZ, LANG, LC_ALL, LC_CTYPE; optional DOZZLE_AUTH_PROVIDER, DOZZLE_AUTH_USERNAME, DOZZLE_AUTH_PASSWORD.
- **diun** – TZ, LANG, LC_ALL, LC_CTYPE; DIUN_WATCH_*, DIUN_PROVIDERS_DOCKER; DIUN_NOTIF_* for notifiers (see stack .env.example).
- **infisical** – TZ, LANG, LC_ALL, LC_CTYPE (backend); ENCRYPTION_KEY, AUTH_SECRET, POSTGRES_*, DB_CONNECTION_URI, REDIS_URL, SITE_URL; optional SMTP_*, OAuth CLIENT_* (see stack .env.example).
- **grafana** – TZ, LANG, LC_ALL, LC_CTYPE; optional GF_SERVER_ROOT_URL (when behind Caddy), GF_USERS_ALLOW_SIGN_UP, GF_SECURITY_*.
- **prometheus** – TZ, LANG, LC_ALL, LC_CTYPE; config via prometheus.yml (no env secrets).
- **cadvisor** – TZ, LANG, LC_ALL, LC_CTYPE; no config files.
- **password-pusher** – TZ (optional); PWPUSH_MASTER_KEY (required); optional PWP__HOST_DOMAIN, PWP__HOST_PROTOCOL when behind Caddy; PWP__ENABLE_LOGINS, PWP__PURGE_AFTER (see stack .env.example).
- **yourls** – TZ (optional); YOURLS_SITE (required, must match Caddy hostname); YOURLS_USER, YOURLS_PASS, YOURLS_COOKIEKEY; YOURLS_DB_PASSWORD, YOURLS_DB_ROOT_PASSWORD; optional YOURLS_DB_NAME, YOURLS_DB_USER (see stack .env.example).
- **linkstack** – TZ (optional); optional SERVER_ADMIN, HTTP_SERVER_NAME, HTTPS_SERVER_NAME, LOG_LEVEL, PHP_MEMORY_LIMIT, UPLOAD_MAX_FILESIZE (see stack .env.example).
- **ollama** – TZ, LANG, LC_ALL, LC_CTYPE; OLLAMA_HOST_PORT; OLLAMA_MODELS_PATH (path for models; use absolute path for large storage). Other data uses Docker volume `ollama_data`. GPU: requires NVIDIA Container Toolkit; no API keys.
- **open-notebook** – TZ, LANG, LC_ALL, LC_CTYPE; OPEN_NOTEBOOK_ENCRYPTION_KEY (required; generate with `openssl rand -base64 32`); SURREAL_USER, SURREAL_PASSWORD, SURREAL_NAMESPACE, SURREAL_DATABASE; OLLAMA_BASE_URL (optional; e.g. http://ollama:11434 or http://host.docker.internal:11434). See stack .env.example.
- **perplexica** – TZ, LANG, LC_ALL, LC_CTYPE; PERPLEXICA_HOST_PORT, PERPLEXICA_DATA_PATH; optional SEARXNG_API_URL (leave empty for bundled SearxNG), OLLAMA_BASE_URL. See stack .env.example.
- **open-webui** – TZ, LANG, LC_ALL, LC_CTYPE; OPEN_WEBUI_HOST_PORT; OLLAMA_BASE_URL (required for Ollama; e.g. http://ollama:11434 or http://host.docker.internal:11434); optional OPENAI_API_KEY, ENABLE_SIGNUP, DEFAULT_USER_ROLE, WEBUI_SECRET_KEY, WEBUI_JWT_SECRET_KEY. See stack .env.example.
- **librechat** – TZ, LANG, LC_ALL, LC_CTYPE; LIBRECHAT_HOST_PORT, MONGODB_*, REDIS_*; MONGO_INITDB_ROOT_USERNAME, MONGO_INITDB_ROOT_PASSWORD, REDIS_PASSWORD; DOMAIN_CLIENT, DOMAIN_SERVER; OLLAMA_BASE_URL; optional OPENAI_API_KEY; JWT_SECRET, JWT_REFRESH_SECRET (required for production; generate with `openssl rand -base64 32`); ALLOW_REGISTRATION, ALLOW_SOCIAL_LOGIN. See stack .env.example.
- **n8n** – TZ, LANG, LC_ALL, LC_CTYPE; N8N_HOST, WEBHOOK_URL (required when behind Caddy; set to your base URL e.g. https://n8n.home or https://n8n.bolens.dev); N8N_PORT=5678, N8N_PROTOCOL=https; optional N8N_ENCRYPTION_KEY (e.g. `openssl rand -hex 32`). No host ports; access via Caddy only. See stack .env.example.
