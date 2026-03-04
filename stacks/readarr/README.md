# Readarr

Book and audiobook collection manager for Usenet and torrents. Readarr monitors authors and series, grabs releases from indexers, and organizes your book library.

**Website:** https://readarr.com/  
**Docs:** https://wiki.servarr.com/readarr  
**Docker guide:** https://wiki.servarr.com/docker-guide

## Quick start

1. **Shared networks and volumes** (if not already created):
   ```bash
   docker network create usenet
   docker network create torrents
   docker volume create usenet_downloads
   docker volume create torrents_downloads
   docker volume create media_books
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
   - Access Readarr via Caddy (for example `https://readarr.home` or `https://readarr.yourdomain.com`).
   - Configure:
     - **Download client**: NZBGet and/or qBittorrent.
     - **Indexers**: from Prowlarr/NZBHydra 2.
     - **Root folder**: `/books` (shared `media_books` volume).

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `readarr:8787`)         |
| **Networks** | `monitor`, `usenet`, `torrents`, plus default                         |
| **Image**  | `lscr.io/linuxserver/readarr:nightly`                                  |
| **Env**    | `TZ`, `PUID`, `PGID`, optional `READARR__*`                             |
| **Storage**| `readarr_config` → `/config`, `media_books` → `/books`, downloads volumes → `/downloads`, `/torrents` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
readarr.home, readarr.local {
  tls internal
  reverse_proxy readarr:8787
}
```

