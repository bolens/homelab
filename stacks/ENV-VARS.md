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

- **portainer** – (Portainer CE; add TZ/LANG if you ever customize it.)
- **watchtower** – TZ, LANG, LC_ALL, LC_CTYPE.
- **caddy** – TZ, LANG, LC_ALL, LC_CTYPE.
- **uptime-kuma** – TZ, LANG, LC_ALL, LC_CTYPE.
- **cloudflare-tunnel** – TZ, LANG, LC_ALL, LC_CTYPE.
