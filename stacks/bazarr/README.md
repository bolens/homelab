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
     - Your TV and movie folders: `/data/tv` and `/data/movies` (the same container paths Sonarr and Radarr report).
   - Configure subtitle languages and providers.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `bazarr:6767`)          |
| **Networks** | `ingress-admin` plus default                                                |
| **Image**  | `lscr.io/linuxserver/bazarr:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`, `BAZARR_TV_PATH`, `BAZARR_MOVIES_PATH`           |
| **Storage**| `bazarr_config` → `/config`, `${BAZARR_TV_PATH}` → `/data/tv`, `${BAZARR_MOVIES_PATH}` → `/data/movies` |

The container is limited to one CPU. Automatic subtitle synchronization can
still extract and resample audio with ffmpeg, but that background work cannot
consume multiple host cores. If synchronization throughput is more important
than host responsiveness, raise `cpus` deliberately.

## Performance and provider troubleshooting

- Repeated `tvsubtitles.net` name-resolution warnings indicate that the
  TVSubtitles provider is unavailable. Remove **TVSubtitles** under
  **Settings → Providers** so Bazarr does not retry it every ten minutes.
- This repository runs Plex with host networking. Configure Bazarr's Plex
  integration with `http://host.docker.internal:32400`; the Compose stack maps
  that name to the Docker host. Avoid a discovered `plex.direct` address when
  it is unreachable from Docker bridge networks.
- Automatic subtitle synchronization reads and resamples media audio. Disable
  or narrow it under **Settings → Subtitles → Automatic Subtitles
  Synchronization** if the one-core background cost is still undesirable.
- Embedded-subtitle discovery also reads media containers. On slower or remote
  storage, consider disabling **Use Embedded Subtitles** under **Settings →
  Subtitles → Performance / Optimization**.

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
bazarr.home, bazarr.local {
  tls internal
  reverse_proxy bazarr:6767
}
```
