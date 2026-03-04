# Radarr

Movie collection manager for Usenet and torrents. Radarr monitors your wanted movies, grabs releases from NZB/torrent indexers, sends them to download clients, and organizes the resulting files.

**Website:** https://radarr.video/  
**Docs:** https://wiki.servarr.com/radarr  
**Docker guide:** https://wiki.servarr.com/docker-guide

## Quick start

1. **Shared networks and volumes** (if not already created):
   ```bash
   docker network create usenet
   docker network create torrents
   docker volume create usenet_downloads
   docker volume create torrents_downloads
   docker volume create media_movies
   ```
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, and `PGID`.
3. **Deploy**
   - From this directory:
     ```bash
     docker compose up -d
     ```
4. **First run**
   - Access Radarr via Caddy (for example `https://radarr.home` or `https://radarr.yourdomain.com`).
   - Configure:
     - **Download client**: NZBGet (`http://nzbget:6789`) and/or qBittorrent (`http://qbittorrent:8080`).
     - **Indexers**: from Prowlarr/NZBHydra 2.
     - **Root folder**: `/movies` (shared `media_movies` volume).

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `radarr:7878`)          |
| **Networks** | `monitor`, `usenet`, `torrents`, plus default                         |
| **Image**  | `lscr.io/linuxserver/radarr:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`, optional `RADARR__*`                              |
| **Storage**| `radarr_config` → `/config`, `media_movies` → `/movies`, downloads volumes → `/downloads`, `/torrents` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
radarr.home, radarr.local {
  tls internal
  reverse_proxy radarr:7878
}
```

