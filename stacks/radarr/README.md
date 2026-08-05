# Radarr

Movie collection manager for Usenet and torrents. Radarr monitors your wanted movies, grabs releases from NZB/torrent indexers, sends them to download clients, and organizes the resulting files.

**Website:** https://radarr.video/  
**Docs:** https://wiki.servarr.com/radarr  
**GitHub:** https://github.com/Radarr/Radarr  
**Docker image:** https://hub.docker.com/r/linuxserver/radarr  
**Releases:** https://github.com/Radarr/Radarr/releases  

## Quick start

1. **Shared networks and torrent download volume** (if not already created):
   ```bash
   docker network create usenet
   docker network create torrents
   mkdir -p /mnt/unraid/media/movies /mnt/unraid/media/downloads/{usenet,torrents}
   ```
   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, and `PGID`.
   - Confirm `RADARR_MEDIA_PATH` (default `/mnt/unraid/media`).
3. **Deploy**
   - From this directory:
     ```bash
     docker compose --env-file stack.env up -d
     ```
4. **First run**
   - Access Radarr via Caddy (for example `https://radarr.home` or `https://radarr.yourdomain.com`).
   - Configure:
     - **Download client**: NZBGet (`http://nzbget:6789`) and/or qBittorrent (`http://qbittorrent:8080`).
     - **Indexers**: from Prowlarr/NZBHydra 2.
     - **Root folder**: `/data/movies`.
     - **NZBGet remote path mapping**: host `nzbget`, remote
       `/downloads/`, local `/data/downloads/usenet/`.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `radarr:7878`)          |
| **Networks** | `ingress-admin`, `usenet`, `torrents`, plus default                         |
| **Image**  | `lscr.io/linuxserver/radarr:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`, `RADARR_MEDIA_PATH`, optional `RADARR__*` |
| **Storage**| `radarr_config` → `/config`, `${RADARR_MEDIA_PATH}` → `/data`; use `/data/movies` and `/data/downloads/*` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
radarr.home, radarr.local {
  tls internal
  reverse_proxy radarr:7878
}
```
