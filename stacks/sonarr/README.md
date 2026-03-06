# Sonarr

TV series management for Usenet and torrents. Sonarr monitors your library, grabs new episodes from NZB/torrent indexers, sends them to your download clients, and organizes the resulting files.

**Website:** https://sonarr.tv/  
**Docs:** https://wiki.servarr.com/sonarr  
**GitHub:** https://github.com/Sonarr/Sonarr  
**Docker image:** https://hub.docker.com/r/linuxserver/sonarr  
**Releases:** https://github.com/Sonarr/Sonarr/releases  

## Quick start

1. **Shared networks and volumes** (once per host, if not already present):
   ```bash
   docker network create usenet
   docker network create torrents
   docker volume create usenet_downloads
   docker volume create torrents_downloads
   docker volume create media_tv
   ```
   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set:
     - `TZ` to your timezone.
     - `PUID` / `PGID` to the user/group that should own media files.
3. **Deploy**
   - From this directory:
     ```bash
     docker compose up -d
     ```
4. **First run**
   - Access Sonarr via Caddy (for example `https://sonarr.home` or `https://sonarr.yourdomain.com`).
   - Add:
     - **Download client**: NZBGet at `http://nzbget:6789` and/or qBittorrent at `http://qbittorrent:8080`.
     - **Indexers**: from Prowlarr/NZBHydra 2.
     - **Root folder**: `/tv` (points at the shared `media_tv` volume).

This stack uses a **config volume** (`sonarr_config`), a shared **TV media volume** (`media_tv`), and shared **download volumes** (`usenet_downloads`, `torrents_downloads`) so it can coordinate with NZBGet and qBittorrent.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `sonarr:8989`)          |
| **Networks** | `monitor`, `usenet`, `torrents`, plus the stack’s default network     |
| **Image**  | `lscr.io/linuxserver/sonarr:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`, optional `SONARR__*` settings                    |
| **Storage**| `sonarr_config` → `/config`, `media_tv` → `/tv`, downloads volumes → `/downloads`, `/torrents` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
sonarr.home, sonarr.local {
  tls internal
  reverse_proxy sonarr:8989
}
```

For public access via Cloudflare Tunnel, add a `sonarr.yourdomain.com` block in the public HTTPS section of your Caddyfile and optionally protect it with Cloudflare Access.

