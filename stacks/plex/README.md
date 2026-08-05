# Plex

Self-hosted media server for movies, TV shows, and music. Plex serves your media library to web, mobile, TV apps, and other clients.

**Website:** https://www.plex.tv/  
**Docs:** https://support.plex.tv/  
**Docker image:** https://hub.docker.com/r/linuxserver/plex  
**Releases:** https://support.plex.tv/articles/205165398-plex-media-server-release-notes/  

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set:
     - `TZ` to your timezone.
     - `PUID` / `PGID` to the user/group that should own media and metadata.
     - Confirm media paths (defaults `/mnt/unraid/media/{tv,movies,music}`).
     - Optionally `PLEX_CLAIM` with a claim token from Plex (first run only).
2. **Deploy**
   - From this directory:
     ```bash
     docker compose up -d
     ```
3. **First run**
   - Browse to `http://<docker-host>:32400/web` and complete the Plex setup.
   - Add libraries pointing to:
     - `/data/tv` for TV shows.
     - `/data/movies` for movies.
     - `/data/music` for music.

Media libraries are bind-mounted from the same host paths used by Sonarr/Radarr/Lidarr (defaults under `/mnt/unraid/media/`).
An idempotent startup hook ensures the named `/transcode` volume remains
writable by the configured `PUID`/`PGID`.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Direct via `http://host:32400/web`, or via Caddy reverse proxy         |
| **Network**| `network_mode: host` (no `monitor` network needed)                     |
| **Image**  | `lscr.io/linuxserver/plex:latest`                                      |
| **Env**    | `TZ`, `PUID`, `PGID`, `VERSION=docker`, `PLEX_*_PATH`, optional `PLEX_CLAIM` |
| **Storage**| `plex_config` → `/config`, `plex_transcode` → `/transcode`, host media paths → `/data/{tv,movies,music}` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
plex.home, plex.local {
  tls internal
  reverse_proxy host.docker.internal:32400
}
```

For public access, add `plex.yourdomain.com` to your Caddyfile and Cloudflare Tunnel, then protect it with Cloudflare Access.
