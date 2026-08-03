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
   mkdir -p /mnt/unraid/media/music /mnt/unraid/media/downloads/usenet/completed/music
   ```
   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, and `PGID`.
   - Confirm `LIDARR_MEDIA_PATH` (default `/mnt/unraid/media`).
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
     - **Root folder**: `/data/music`.
     - **NZBGet remote path mapping**: host `nzbget`, remote
       `/downloads/`, local `/data/downloads/usenet/`.
   - Under **Settings → Download Clients**, disable **Completed Download
     Handling**. This leaves releases in NZBGet's `music` category instead of
     importing them directly into the published library.
   - In Picard, load those releases from `/lidarr-intake`, tag them, and
     save/move them to `/music`. Lidarr detects them during its next library
     scan; Navidrome and Soulseek see them only after this move.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `lidarr:8686`)          |
| **Networks** | `monitor`, `usenet`, `torrents`, plus default                         |
| **Image**  | `lscr.io/linuxserver/lidarr:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`, `LIDARR_MEDIA_PATH`, optional `LIDARR__*` |
| **Storage**| `lidarr_config` → `/config`, `${LIDARR_MEDIA_PATH}` → `/data`; use `/data/music` and `/data/downloads/*` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
lidarr.home, lidarr.local {
  tls internal
  reverse_proxy lidarr:8686
}
```
