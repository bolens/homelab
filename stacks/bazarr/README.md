# Bazarr

Bazarr is a subtitle manager and downloader for Sonarr and Radarr. It automatically searches for subtitles in your preferred languages and keeps them up to date for your TV and movie library.

**Website:** https://www.bazarr.media/  
**Docs:** https://www.bazarr.media/docs  
**GitHub:** https://github.com/morpheus65535/bazarr  
**Docker image:** https://hub.docker.com/r/linuxserver/bazarr  
**Releases:** https://github.com/morpheus65535/bazarr/releases  

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, and `PGID`.
   - Confirm `BAZARR_TV_PATH` / `BAZARR_MOVIES_PATH` (defaults `/mnt/unraid/media/tv` and `/mnt/unraid/media/movies`).
2. **Deploy**
   - From this directory:
     ```bash
     docker compose up -d
     ```
3. **First run**
   - Access Bazarr via Caddy (for example `https://bazarr.home` or `https://bazarr.yourdomain.com`).
   - Point Bazarr at:
     - The Sonarr and Radarr APIs.
     - Your TV and movie folders: `/tv` and `/movies` (same host paths as Sonarr/Radarr).
   - Configure subtitle languages and providers.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `bazarr:6767`)          |
| **Networks** | `monitor` plus default                                                |
| **Image**  | `lscr.io/linuxserver/bazarr:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`, `BAZARR_TV_PATH`, `BAZARR_MOVIES_PATH`           |
| **Storage**| `bazarr_config` → `/config`, `${BAZARR_TV_PATH}` → `/tv`, `${BAZARR_MOVIES_PATH}` → `/movies` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
bazarr.home, bazarr.local {
  tls internal
  reverse_proxy bazarr:6767
}
```

