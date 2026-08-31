# Jellystat

[Jellystat](https://github.com/CyferShepard/Jellystat) is a free, open-source statistics app for [Jellyfin](https://jellyfin.org/) (session monitoring, libraries, watch history, and related metrics). This stack runs the official [Docker image](https://hub.docker.com/r/cyfershepard/jellystat) with a dedicated PostgreSQL instance.

## Quick start

1. From this directory, run `./prepare-stack.sh` (or copy `stack.env.example` → `stack.env` and `caddy_snippet.conf.example` → `caddy_snippet.conf`).
2. Edit `stack.env`: set `POSTGRES_PASSWORD` and `JWT_SECRET` (see placeholders in `stack.env.example`). Ensure [shared env](../../documents/SHARED-RESOURCES.md) provides `TZ`, or set `TZ` in `stack.env`.
3. Adjust `caddy_snippet.conf` hostnames to match your domain, then reload Caddy so it imports this snippet.
4. Deploy: `docker compose up -d`.

**Portainer:** Stacks → Add stack → paste `docker-compose.yml`, set the same variables in the stack environment or an env file.

## Access

- **Public URL (example):** `https://jellystat.example.com`, replace with your real hostname in local Caddy config only.
- **Internal:** `http://jellystat:3000` on `ingress-admin` from Caddy.

## Jellyfin connection

After the web UI loads, complete setup and add your Jellyfin server:

- If Jellyfin runs on the same host and `media-services`, use `http://jellyfin:8096` as the server URL.
- If Jellystat must use the same URL as browsers (cookies/HTTPS), use your public Jellyfin URL instead.

Optional env (see upstream README): `IS_EMBY_API`, `JF_USE_WEBSOCKETS`, `REJECT_SELF_SIGNED_CERTIFICATES`, MaxMind keys for IP geolocation.

## Health and monitoring

- Compose healthcheck uses `GET /auth/isConfigured` on port 3000 (same as upstream).
- Swagger/API docs: `/swagger` (when enabled by the app).

## Volumes

| Volume              | Purpose                          |
|---------------------|----------------------------------|
| `jellystat_postgres` | PostgreSQL data                 |
| `jellystat_backup`   | App backup/export directory     |

## Links

- [GitHub, CyferShepard/Jellystat](https://github.com/CyferShepard/Jellystat)
- [Docker Hub, cyfershepard/jellystat](https://hub.docker.com/r/cyfershepard/jellystat)
