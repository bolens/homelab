# Bazarr

Bazarr is a subtitle manager and downloader for Sonarr and Radarr. It automatically searches for subtitles in your preferred languages and keeps them up to date for your TV and movie library.

**Website:** https://www.bazarr.media/  
**Docs:** https://www.bazarr.media/docs

## Quick start

1. **Shared media volumes** (if not already created):
   ```bash
   docker volume create media_tv
   docker volume create media_movies
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
   - Access Bazarr via Caddy (for example `https://bazarr.home` or `https://bazarr.yourdomain.com`).
   - Point Bazarr at:
     - The Sonarr and Radarr APIs.
     - Your TV and movie folders: `/tv` and `/movies`.
   - Configure subtitle languages and providers.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `bazarr:6767`)          |
| **Networks** | `monitor` plus default                                                |
| **Image**  | `lscr.io/linuxserver/bazarr:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`                                                   |
| **Storage**| `bazarr_config` → `/config`, `media_tv` → `/tv`, `media_movies` → `/movies` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
bazarr.home, bazarr.local {
  tls internal
  reverse_proxy bazarr:6767
}
```

