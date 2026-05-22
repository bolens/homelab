# Umami

[Umami](https://umami.is/) is a self-hosted, privacy-focused web analytics dashboard. You add websites in the UI, embed a small `script.js` on pages you want to measure, and view traffic in Umami.

## Quick start

1. From this directory: `./prepare-stack.sh` (creates `stack.env` and `caddy_snippet.conf` from the `.example` files when missing). Postgres and the Umami app read **`stack.env` via `env_file`** only — no project `.env` symlink required.
2. Edit `stack.env`: set `POSTGRES_PASSWORD` and `APP_SECRET` (see comments in `stack.env.example`).
3. Replace hostnames in `caddy_snippet.conf` with yours (the committed `.example` uses placeholders only).
4. Reload Caddy so it picks up the snippet, then:

   ```bash
   docker compose up -d
   ```

**Portainer:** Add stack → paste `docker-compose.yml` → set the same variables from `stack.env.example` in the Portainer env UI (or upload `stack.env`).

## URLs and Caddy

- No host ports are published. The app listens on **3000** inside Docker; [stacks/caddy](../caddy/) reverse-proxies to `umami:3000` on the external **`monitor`** network.
- After `prepare-stack.sh`, edit `caddy_snippet.conf` and reload Caddy.

## First login

Umami creates a default administrator: **username `admin`**, **password `umami`**. Log in once and change the password under **Profile → Settings → Change password** ([docs](https://umami.is/docs/login)).

## Tracking other sites

In Umami, add a website to get a **Website ID** and script URL. For apps in this repo (for example [stacks/nodepad](../nodepad/README.md)), set `UMAMI_SCRIPT_URL` and `UMAMI_WEBSITE_ID` if the app supports it.

The tracker endpoint must be reachable from visitors’ browsers (same hostname as your public site, or a dedicated analytics subdomain). The **admin dashboard** should stay behind Caddy and, if you use it, Cloudflare Access.

## Health checks

- `GET /api/heartbeat` — returns 200 when the app is up (used by the container healthcheck).

## Data and backups

- Postgres data lives in the **`umami_pg_data`** named volume. Include it in your backup strategy if analytics history matters.

## Links

- [Documentation](https://umami.is/docs)
- [GitHub](https://github.com/umami-software/umami)
- [Environment variables](https://umami.is/docs/environment-variables)
