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
