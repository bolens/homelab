# Explo - music discovery automation

[Explo](https://github.com/LumePart/Explo) is a scheduled discovery worker for self-hosted music systems. It fetches personalized recommendations (ListenBrainz) and requests tracks from YouTube and/or Soulseek into your library.

This stack is a **worker/CLI-style service** (cron inside the container), not a web app. It does **not** need a Caddy vhost.

**Website / repo:** https://github.com/LumePart/Explo  
**Docs wiki:** https://github.com/LumePart/Explo/wiki  
**Docker image:** https://ghcr.io/lumepart/explo  

## Quick start

1. Run `./prepare-stack.sh` from this directory (creates `stack.env`, ensures
   the private `media-services` network, and ensures shared storage resources).
2. Edit `stack.env` and set at least:
   - `LISTENBRAINZ_USER`
   - `EXPLO_SYSTEM`
   - `SYSTEM_URL`, `SYSTEM_USERNAME`, `SYSTEM_PASSWORD`
   - `DOWNLOAD_SERVICES`
   - `YOUTUBE_API_KEY` (if using `youtube`)
3. Deploy:

   ```bash
   docker compose up -d
   ```

4. Check logs to confirm scheduled jobs were registered:

   ```bash
   docker compose logs -f explo
   ```

## Configuration

| Item | Details |
| ---- | ------- |
| **Type** | Scheduled worker (no web UI) |
| **Network** | Private `media-services` for Navidrome and Soulseek plus a default network for outbound APIs |
| **Image** | `ghcr.io/lumepart/explo:latest` |
| **Config** | `./stack.env` is both loaded as env and mounted as `/opt/explo/.env` |
| **Storage** | Shared host music path `${MUSIC_LIBRARY_PATH}` mounted at `/data`; slskd source path `${SLSKD_DOWNLOADS_PATH}` mounted at `/slskd` |

## Integrations

- **ListenBrainz:** recommendation source (`LISTENBRAINZ_USER` required).
- **Music system:** set `EXPLO_SYSTEM` + `SYSTEM_URL` + credentials for Navidrome/Jellyfin/Emby/Plex/Subsonic/MPD support (see upstream docs for system-specific requirements).
- **Soulseek/slskd:** set `SLSKD_URL`, `SLSKD_API_KEY`, `SLSKD_DOWNLOADS_PATH`, and `MIGRATE_DOWNLOADS=true` so completed slskd downloads can be moved into the shared Navidrome music library.

## Portainer

Create the stack from this directory. Run `./prepare-stack.sh` first so `stack.env` and local data paths exist. This stack does not expose HTTP ports and does not require Caddy routing.
