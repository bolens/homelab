# Plex

Self-hosted media server for movies, TV shows, and music. Plex serves your media library to web, mobile, TV apps, and other clients.

**Website:** https://www.plex.tv/  
**Docs:** https://support.plex.tv/  
**Docker image:** https://hub.docker.com/r/linuxserver/plex  
**Releases:** https://support.plex.tv/articles/205165398-plex-media-server-release-notes/  

## Quick start

1. **Media volumes** (if not already created):
   ```bash
   docker volume create media_tv
   docker volume create media_movies
   docker volume create media_music
   ```
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set:
     - `TZ` to your timezone.
     - `PUID` / `PGID` to the user/group that should own media and metadata.
     - Optionally `PLEX_CLAIM` with a claim token from Plex (first run only).
3. **Deploy**
   - From this directory:
     ```bash
     docker compose up -d
     ```
4. **First run**
   - Browse to `http://<docker-host>:32400/web` and complete the Plex setup.
   - Add libraries pointing to:
     - `/data/tv` for TV shows.
     - `/data/movies` for movies.
     - `/data/music` for music.

This stack uses **host networking** so Plex can discover clients and expose the standard Plex ports on the Docker host. Media is mounted via shared `media_*` volumes used by Sonarr/Radarr/Lidarr/Readarr.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Direct via `http://host:32400/web`, or via Caddy reverse proxy         |
| **Network**| `network_mode: host` (no `monitor` network needed)                     |
| **Image**  | `lscr.io/linuxserver/plex:latest`                                      |
| **Env**    | `TZ`, `PUID`, `PGID`, `VERSION=docker`, optional `PLEX_CLAIM`          |
| **Storage**| `plex_config` → `/config`, `plex_transcode` → `/transcode`, `media_tv` → `/data/tv`, `media_movies` → `/data/movies`, `media_music` → `/data/music` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
plex.home, plex.local {
  tls internal
  reverse_proxy host.docker.internal:32400
}
```

For public access, add `plex.yourdomain.com` to your Caddyfile and Cloudflare Tunnel, then protect it with Cloudflare Access.

