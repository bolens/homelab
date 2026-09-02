# Jellyfin

Open-source media server for movies, TV shows, and music. Jellyfin serves your media library to web, mobile, and TV apps with no proprietary cloud dependency.

**Website:** https://jellyfin.org/  
**Docs:** https://jellyfin.org/docs/  
**GitHub:** https://github.com/jellyfin/jellyfin  
**Docker image:** https://hub.docker.com/r/linuxserver/jellyfin  
**Releases:** https://github.com/jellyfin/jellyfin/releases  

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, and `PGID` to match your host user/group.
   - Confirm media paths (defaults below `/mnt/unraid/media`).
2. **Deploy**
   - From this directory:
     ```bash
     docker compose up -d
     ```
3. **First run**
   - Access Jellyfin via Caddy (see vhost example below).
   - Add libraries pointing to:
     - `/data/tv` for TV shows.
     - `/data/movies` for movies.
     - `/data/music` for music.
     - `/data/audiobooks` for audiobooks.
     - `/data/books` for the scanner-safe Calibre export.

The stack keeps the HTTP UI internal and uses `ingress-public` for Caddy plus `media-services` for trusted media integrations.
An idempotent startup hook ensures the named `/cache` volume remains writable
by the configured `PUID`/`PGID`.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host ports; reverse-proxy to `jellyfin:8096`)       |
| **Network**| `ingress-public` plus `media-services`                                  |
| **Image**  | `lscr.io/linuxserver/jellyfin:latest`                                  |
| **Env**    | `TZ`, `PUID`, `PGID`, and the `JELLYFIN_*_PATH` library paths |
| **Storage**| Local config/cache; host media → `/data/{tv,movies,music,audiobooks,books}`; books and audiobooks are read-only |

`/data/books` defaults to `/mnt/unraid/media/kavita-books`, the automated
Calibre Save-to-Disk export. This avoids scanning Calibre's private live
library layout and gives Jellyfin the same normalized copies as Kavita.

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
jellyfin.home, jellyfin.local {
  tls internal
  reverse_proxy jellyfin:8096
}
```

For public access via Cloudflare Tunnel, add e.g. `jellyfin.yourdomain.com` in the public HTTPS section of your Caddyfile and protect it with Cloudflare Access if desired.
