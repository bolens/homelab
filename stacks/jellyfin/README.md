# Jellyfin

Open-source media server for movies, TV shows, and music. Jellyfin serves your media library to web, mobile, and TV apps with no proprietary cloud dependency.

**Website:** https://jellyfin.org/  
**Docs:** https://jellyfin.org/docs/  
**GitHub:** https://github.com/jellyfin/jellyfin  
**Docker image:** https://hub.docker.com/r/linuxserver/jellyfin  
**Releases:** https://github.com/jellyfin/jellyfin/releases  

## Quick start

1. **Media volumes** (if not already created):
   ```bash
   docker volume create media_tv
   docker volume create media_movies
   docker volume create media_music
   ```
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, and `PGID` to match your host user/group.
3. **Deploy**
   - From this directory:
     ```bash
     docker compose up -d
     ```
4. **First run**
   - Access Jellyfin via Caddy (see vhost example below).
   - Add libraries pointing to:
     - `/data/tv` for TV shows.
     - `/data/movies` for movies.
     - `/data/music` for music.

The stack keeps the HTTP UI internal (no host port binding) and relies on Caddy on the shared `monitor` network for access.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host ports; reverse-proxy to `jellyfin:8096`)       |
| **Network**| `monitor` plus default                                                  |
| **Image**  | `lscr.io/linuxserver/jellyfin:latest`                                  |
| **Env**    | `TZ`, `PUID`, `PGID`                                                   |
| **Storage**| `jellyfin_config` → `/config`, `jellyfin_cache` → `/cache`, `media_*` → `/data/...` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
jellyfin.home, jellyfin.local {
  tls internal
  reverse_proxy jellyfin:8096
}
```

For public access via Cloudflare Tunnel, add e.g. `jellyfin.yourdomain.com` in the public HTTPS section of your Caddyfile and protect it with Cloudflare Access if desired.

