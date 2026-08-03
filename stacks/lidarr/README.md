# Lidarr

Music collection manager for Usenet and torrents. Lidarr tracks artists and albums, grabs them from NZB/torrent indexers, and keeps your library organized.

**Website:** https://lidarr.audio/  
**Docs:** https://wiki.servarr.com/lidarr  
**GitHub:** https://github.com/Lidarr/Lidarr  
**Docker image:** https://hub.docker.com/r/linuxserver/lidarr  
**Releases:** https://github.com/Lidarr/Lidarr/releases  

## Quick start

1. **Shared networks and torrent download volume** (if not already created):
   ```bash
   docker network create usenet
   docker network create torrents
   docker volume create torrents_downloads
   mkdir -p /mnt/unraid/media/music /mnt/unraid/media/downloads/usenet
   ```
   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, and `PGID`.
   - Confirm `LIDARR_MUSIC_PATH` (default `/mnt/unraid/media/music`).
   - Confirm `LIDARR_USENET_DOWNLOADS_PATH` (default `/mnt/unraid/media/downloads/usenet`).
3. **Deploy**
   - From this directory:
     ```bash
     docker compose --env-file stack.env up -d
     ```
4. **First run**
   - Access Lidarr via Caddy (for example `https://lidarr.home` or `https://lidarr.yourdomain.com`).
   - Configure:
     - **Download client**: NZBGet and/or qBittorrent.
     - **Indexers**: from Prowlarr/NZBHydra 2.
     - **Root folder**: `/music` (bind-mounted from `LIDARR_MUSIC_PATH`).

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `lidarr:8686`)          |
| **Networks** | `monitor`, `usenet`, `torrents`, plus default                         |
| **Image**  | `lscr.io/linuxserver/lidarr:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`, `LIDARR_MUSIC_PATH`, `LIDARR_USENET_DOWNLOADS_PATH`, optional `LIDARR__*` |
| **Storage**| `lidarr_config` → `/config`, `${LIDARR_MUSIC_PATH}` → `/music`, `${LIDARR_USENET_DOWNLOADS_PATH}` → `/downloads`, `torrents_downloads` → `/torrents` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
lidarr.home, lidarr.local {
  tls internal
  reverse_proxy lidarr:8686
}
```

