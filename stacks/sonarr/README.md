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
   mkdir -p /mnt/unraid/media/tv /mnt/unraid/media/downloads/{usenet,torrents}
   ```
   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set:
     - `TZ` to your timezone.
     - `PUID` / `PGID` to the user/group that should own media files.
     - Confirm `SONARR_MEDIA_PATH` (default `/mnt/unraid/media`).
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
     - **Root folder**: `/data/tv`.
     - **NZBGet remote path mapping**: host `nzbget`, remote
       `/downloads/`, local `/data/downloads/usenet/`.

This stack mounts the entire media tree once at `/data`. Keeping downloads and
the TV library below one container mount enables atomic Usenet moves and
hardlinked torrent imports.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `sonarr:8989`)          |
| **Networks** | `ingress-admin`, `usenet`, `torrents`, plus the stack's default network     |
| **Image**  | `lscr.io/linuxserver/sonarr:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`, `SONARR_MEDIA_PATH`, optional `SONARR__*` |
| **Storage**| `sonarr_config` → `/config`, `${SONARR_MEDIA_PATH}` → `/data` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
sonarr.home, sonarr.local {
  tls internal
  reverse_proxy sonarr:8989
}
```

For public access via Cloudflare Tunnel, add a `sonarr.yourdomain.com` block in the public HTTPS section of your Caddyfile and optionally protect it with Cloudflare Access.
