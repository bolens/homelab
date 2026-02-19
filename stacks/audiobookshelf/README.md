# Podcast (Audiobookshelf)

Self-hosted podcast (and audiobook) server: subscribe to podcasts, stream or download episodes, sync progress across web and mobile apps.

**Website:** https://www.audiobookshelf.org  
**Docs:** https://www.audiobookshelf.org/faq/server  
**GitHub:** https://github.com/advplyr/audiobookshelf

## Quick start

1. **Environment**
   - Copy `.env.example` to `.env`.
   - Set `TZ` to your timezone if different from America/Denver.
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer and set the same vars in the stack Environment).
3. **First run:** Open Audiobookshelf via Caddy (e.g. audiobookshelf.home, audiobookshelf.bolens.dev), create the admin account, then add libraries (e.g. Podcasts pointing at `/podcasts`) and subscribe to feeds.

The stack uses **named volumes** (config, metadata, audiobooks, podcasts) so it works when deployed from Portainer’s web editor.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; use audiobookshelf.home, audiobookshelf.bolens.dev, etc.) |
| **Network** | `monitor` (external) — Caddy can reverse-proxy to `audiobookshelf:80` |
| **Image** | ghcr.io/advplyr/audiobookshelf:latest |
| **Env** | `TZ` (optional, default America/Denver) |
| **Storage** | Named volumes: `abs_config`, `abs_metadata`, `abs_audiobooks`, `abs_podcasts` |

## Features

- **Podcasts** – Subscribe by URL or search (iTunes), stream or download, auto-new-episode downloads.
- **Audiobooks** – Add folders under `/audiobooks` (e.g. bind-mount extra host paths if you need more than the default volume).
- **Progress sync** – Web and mobile apps (iOS/Android) sync position and play state.
- **Libraries** – In the UI, add a “Podcast” library with path `/podcasts`, and optionally an “Audiobook” library with path `/audiobooks`.

## Adding more media (bind mounts)

To use host directories for audiobooks or podcasts instead of (or in addition to) the named volumes, add volume mounts to the `audiobookshelf` service, e.g.:

```yaml
volumes:
  - abs_config:/config
  - abs_metadata:/metadata
  - /path/on/host/audiobooks:/audiobooks
  - /path/on/host/podcasts:/podcasts
```

Then add the corresponding library in the Audiobookshelf UI.

## Caddy reverse proxy

Example Caddy vhost (e.g. in your Caddyfile):

```
podcast.yourdomain.com {
  reverse_proxy audiobookshelf:80
}
```

Ensure the podcast stack is on the `monitor` network so Caddy can reach `audiobookshelf:80`.

## Start

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose and optionally set `TZ` in **Environment**.
