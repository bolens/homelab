# RSS reader (FreshRSS)

Self-hosted RSS feed aggregator: subscribe to feeds, categories, star articles, and use extensions. Feedly-like experience with no account limits.

**Website:** https://freshrss.org  
**Docs:** https://docs.linuxserver.io/images/docker-freshrss  
**GitHub:** https://github.com/FreshRSS/FreshRSS

## Quick start

1. **Environment**
   - Copy `.env.example` to `.env`.
   - Set `PUID` / `PGID` if you want volume files owned by a specific user (e.g. `id your_user`); default `1000:1000` is fine for most setups.
   - Set `TZ` to your timezone if different from America/Denver.
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer and set the same vars in the stack Environment).
3. **First run:** Open FreshRSS via Caddy (e.g. freshrss.home, freshrss.bolens.dev), complete the web setup wizard (language, default user, SQLite is pre-configured).

The stack uses a **named volume** (`freshrss_config`) so it works when deployed from Portainer’s web editor.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; use freshrss.home, freshrss.bolens.dev, etc.) |
| **Network** | `monitor` (external) — Caddy can reverse-proxy to `freshrss:80` |
| **Image** | LinuxServer FreshRSS (Alpine + nginx + PHP) |
| **Env** | `PUID`, `PGID`, `TZ` (all optional with defaults) |
| **Storage** | Named volume: `freshrss_config` (config, SQLite DB, extensions) |

## Features

- **Feeds & categories** – Add feeds by URL, organize in categories.
- **Starred / read state** – Mark articles read or starred.
- **Multi-user** – Create multiple users; each has their own feeds (optional).
- **Extensions** – Add extensions under the config volume (see [LinuxServer docs](https://docs.linuxserver.io/images/docker-freshrss)); restart the container to activate.
- **External DB** – The setup wizard can use an existing MySQL/MariaDB instead of built-in SQLite if you prefer.

## Caddy reverse proxy

Example Caddy vhost (e.g. in your Caddyfile):

```
rss.yourdomain.com {
  reverse_proxy freshrss:80
}
```

Ensure the RSS stack is on the `monitor` network so Caddy can reach `freshrss:80`.

## Start

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose and optionally set `PUID`, `PGID`, `TZ` in **Environment**.
