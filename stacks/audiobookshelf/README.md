# Podcast (Audiobookshelf)

Self-hosted podcast (and audiobook) server: subscribe to podcasts, stream or download episodes, sync progress across web and mobile apps.

**Website:** https://www.audiobookshelf.org
**Docs:** https://www.audiobookshelf.org/faq/server
**GitHub:** https://github.com/advplyr/audiobookshelf
**Docker image:** https://github.com/advplyr/audiobookshelf/pkgs/container/audiobookshelf
**Releases:** https://github.com/advplyr/audiobookshelf/releases

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ` to your timezone if different from America/Denver.
   - Confirm `AUDIOBOOKSHELF_AUDIOBOOKS_PATH` (default `/mnt/unraid/media/audiobooks`).
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer and set the same vars in the stack Environment).
3. **First run:** Open Audiobookshelf via Caddy (e.g. audiobookshelf.home, audiobookshelf.yourdomain.com), create the admin account, then add libraries (e.g. Podcasts pointing at `/podcasts`) and subscribe to feeds.

Application state and podcast downloads use local named volumes. The audiobook
library is a read-only bind mount so Bookshelf or another organizer remains the
only service that writes media files.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; use audiobookshelf.home, audiobookshelf.yourdomain.com, etc.) |
| **Network** | `ingress-public` (external), dedicated Caddy-to-service ingress |
| **Image** | ghcr.io/advplyr/audiobookshelf:latest |
| **Env** | `TZ`; `AUDIOBOOKSHELF_AUDIOBOOKS_PATH` defaults to `/mnt/unraid/media/audiobooks` |
| **Storage** | `abs_config` and `abs_metadata` stay local; `${AUDIOBOOKSHELF_AUDIOBOOKS_PATH}` → `/audiobooks` (read-only); `abs_podcasts` → `/podcasts` |

## Features

- **Podcasts** – Subscribe by URL or search (iTunes), stream or download, auto-new-episode downloads.
- **Audiobooks** – Add one audiobook library rooted at `/audiobooks`.
- **Progress sync** – Web and mobile apps (iOS/Android) sync position and play state.
- **Libraries** – In the UI, add a "Podcast" library with path `/podcasts`, and optionally an "Audiobook" library with path `/audiobooks`.

Audiobookshelf does not support `PUID` or `PGID`. The media bind is read-only,
while `/config` and `/metadata` remain local Docker volumes as required for
their SQLite data. If you choose to run the whole container with Compose's
`user:` setting, update the ownership of both named volumes first.

## Caddy reverse proxy

Example Caddy vhost (e.g. in your Caddyfile):

```
podcast.yourdomain.com {
  reverse_proxy audiobookshelf:80
}
```

Ensure the podcast stack is on `ingress-public` so Caddy can reach `audiobookshelf:80`.

## Start

From this directory: `docker compose up -d`.
In Portainer: Stacks → Add stack → paste the compose and optionally set `TZ` in **Environment**.
