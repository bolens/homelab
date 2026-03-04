# Lidarr

Music collection manager for Usenet and torrents. Lidarr tracks artists and albums, grabs them from NZB/torrent indexers, and keeps your library organized.

**Website:** https://lidarr.audio/  
**Docs:** https://wiki.servarr.com/lidarr  
**GitHub:** https://github.com/Lidarr/Lidarr  
**Docker image:** https://hub.docker.com/r/linuxserver/lidarr  
**Releases:** https://github.com/Lidarr/Lidarr/releases  

## Quick start

1. **Shared networks and volumes** (if not already created):
   ```bash
   docker network create usenet
   docker network create torrents
   docker volume create usenet_downloads
   docker volume create torrents_downloads
   docker volume create media_music
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
   - Access Lidarr via Caddy (for example `https://lidarr.home` or `https://lidarr.yourdomain.com`).
   - Configure:
     - **Download client**: NZBGet and/or qBittorrent.
     - **Indexers**: from Prowlarr/NZBHydra 2.
     - **Root folder**: `/music` (shared `media_music` volume).

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `lidarr:8686`)          |
| **Networks** | `monitor`, `usenet`, `torrents`, plus default                         |
| **Image**  | `lscr.io/linuxserver/lidarr:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`, optional `LIDARR__*`                              |
| **Storage**| `lidarr_config` → `/config`, `media_music` → `/music`, downloads volumes → `/downloads`, `/torrents` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
lidarr.home, lidarr.local {
  tls internal
  reverse_proxy lidarr:8686
}
```

