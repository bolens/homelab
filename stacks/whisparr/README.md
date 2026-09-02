# Whisparr

Adult movie collection manager for Usenet and torrents (Servarr family). Monitors indexers, sends grabs to download clients, and organizes files, same workflow as Radarr, separate library and metadata.

**Website:** https://whisparr.com/
**Docs:** https://wiki.servarr.com/whisparr
**GitHub:** https://github.com/Whisparr/Whisparr
**Docker image:** https://github.com/thespad/docker-whisparr (multi-arch `ghcr.io/thespad/whisparr`)

> There is no LinuxServer.io Whisparr image; this stack uses **thespad**'s image (Alpine-based, port **6969**).

## Quick start

1. **Shared networks** (for DNS to NZBGet, qBittorrent, Prowlarr, etc.):
   ```bash
   docker network create usenet
   docker network create torrents
   ```
   See [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) if these already exist on your host.

2. **Environment and host paths**
   - Run `./prepare-stack.sh` (creates `stack.env` from the example and ensures required networks exist).
   - Set `PUID`, `PGID` (or rely on `shared.env` for TZ/locale).
   - Set `WHISPARR_CONFIG_PATH` and the unified `WHISPARR_MEDIA_PATH`.

3. **Deploy:**
   ```bash
   docker compose up -d
   ```

4. **First run**
   - Open `https://whisparr.home` (or your Caddy hostname).
   - Add download clients (e.g. `http://nzbget:6789`,
     `http://qbittorrent:8080`), indexers (Prowlarr), and root folder
     **`/data/adult`**.
   - For NZBGet, map remote `/downloads/` to local
     `/data/downloads/usenet/`.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no published host port); upstream `whisparr:6969` |
| **Networks** | `ingress-admin`, `usenet`, `torrents` |
| **Image** | `ghcr.io/thespad/whisparr:latest` |
| **Env** | `TZ`, `PUID`, `PGID`, `WHISPARR_CONFIG_PATH`, `WHISPARR_MEDIA_PATH` |
| **Storage** | Config bind → `/config`; `${WHISPARR_MEDIA_PATH}` → `/data`; adult library at `/data/adult` |

## Caddy reverse proxy

`caddy_snippet.conf` in this directory proxies `whisparr.home` / `whisparr.local` with internal TLS. For a public hostname, add your own site block (strongly recommend **Cloudflare Access** or equivalent); this UI is not intended to be world-exposed without protection.
