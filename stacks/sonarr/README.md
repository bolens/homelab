# Sonarr

TV series management for Usenet and torrents. Sonarr monitors your library, grabs new episodes from NZB/torrent indexers, sends them to your download clients, and organizes the resulting files.

**Website:** https://sonarr.tv/  
**Docs:** https://wiki.servarr.com/sonarr  
**GitHub:** https://github.com/Sonarr/Sonarr  
**Docker image:** https://hub.docker.com/r/linuxserver/sonarr  
**Releases:** https://github.com/Sonarr/Sonarr/releases  

## Quick start

1. **Shared networks and torrent download volume** (once per host, if not already present):
   ```bash
   docker network create usenet
   docker network create torrents
   docker volume create torrents_downloads
   mkdir -p /mnt/unraid/media/tv /mnt/unraid/media/downloads/usenet
   ```
   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set:
     - `TZ` to your timezone.
     - `PUID` / `PGID` to the user/group that should own media files.
     - Confirm `SONARR_TV_PATH` (default `/mnt/unraid/media/tv`).
     - Confirm `SONARR_USENET_DOWNLOADS_PATH` (default `/mnt/unraid/media/downloads/usenet`).
3. **Deploy**
   - From this directory:
     ```bash
     docker compose --env-file stack.env up -d
     ```
4. **First run**
   - Access Sonarr via Caddy (for example `https://sonarr.home` or `https://sonarr.yourdomain.com`).
   - Add:
     - **Download client**: NZBGet at `http://nzbget:6789` and/or qBittorrent at `http://qbittorrent:8080`.
     - **Indexers**: from Prowlarr/NZBHydra 2.
     - **Root folder**: `/tv` (bind-mounted from `SONARR_TV_PATH`).

This stack uses a **config volume** (`sonarr_config`), a **TV library bind mount** (`SONARR_TV_PATH`), a **Usenet downloads bind mount** (`SONARR_USENET_DOWNLOADS_PATH` → `/downloads`, shared with NZBGet), and the shared **`torrents_downloads`** volume so it can coordinate with qBittorrent.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `sonarr:8989`)          |
| **Networks** | `monitor`, `usenet`, `torrents`, plus the stack’s default network     |
| **Image**  | `lscr.io/linuxserver/sonarr:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`, `SONARR_TV_PATH`, `SONARR_USENET_DOWNLOADS_PATH`, optional `SONARR__*` |
| **Storage**| `sonarr_config` → `/config`, `${SONARR_TV_PATH}` → `/tv`, `${SONARR_USENET_DOWNLOADS_PATH}` → `/downloads`, `torrents_downloads` → `/torrents` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
sonarr.home, sonarr.local {
  tls internal
  reverse_proxy sonarr:8989
}
```

For public access via Cloudflare Tunnel, add a `sonarr.yourdomain.com` block in the public HTTPS section of your Caddyfile and optionally protect it with Cloudflare Access.

