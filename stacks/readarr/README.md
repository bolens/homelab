# Readarr

Book and audiobook collection manager for Usenet and torrents. Readarr monitors authors and series, grabs releases from indexers, and organizes your book library.

**Website:** https://readarr.com/  
**Docs:** https://wiki.servarr.com/readarr  
**GitHub:** https://github.com/Readarr/Readarr  
**Docker image:** https://hub.docker.com/r/linuxserver/readarr  
**Releases:** https://github.com/Readarr/Readarr/releases  

## Quick start

1. **Shared networks and torrent download volume** (if not already created):
   ```bash
   docker network create usenet
   docker network create torrents
   mkdir -p /mnt/unraid/media/books /mnt/unraid/media/downloads/{usenet,torrents}
   ```
   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, and `PGID`.
   - Confirm `READARR_MEDIA_PATH` (default `/mnt/unraid/media`).
3. **Deploy**
   - From this directory:
     ```bash
     docker compose --env-file stack.env up -d
     ```
4. **First run**
   - Access Readarr via Caddy (for example `https://readarr.home` or `https://readarr.yourdomain.com`).
   - Configure:
     - **Download client**: NZBGet and/or qBittorrent.
     - **Indexers**: from Prowlarr/NZBHydra 2.
     - **Root folder**: `/data/books`.
     - **NZBGet remote path mapping**: host `nzbget`, remote
       `/downloads/`, local `/data/downloads/usenet/`.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `readarr:8787`)         |
| **Networks** | `ingress-admin`, `usenet`, `torrents`, plus default                         |
| **Image**  | `lscr.io/linuxserver/readarr:0.4.18-nightly`                            |
| **Env**    | `TZ`, `PUID`, `PGID`, `READARR_MEDIA_PATH`, optional `READARR__*` |
| **Storage**| `readarr_config` → `/config`, `${READARR_MEDIA_PATH}` → `/data`; use `/data/books` and `/data/downloads/*` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
readarr.home, readarr.local {
  tls internal
  reverse_proxy readarr:8787
}
```
