# Mylar3

Automated comic book downloader (CBR/CBZ) for Usenet and torrents. Tracks series, fetches new issues via NZBGet or qBittorrent, and organizes them into a comics folder. Pair with **Komga** by pointing Komga’s library at the same path as Mylar3’s completed comics (e.g. `/comics` or a bind-mounted host path).

**Homepage:** https://mylarcomics.com  
**GitHub:** https://github.com/mylar3/mylar3  
**Docker (LinuxServer):** https://docs.linuxserver.io/images/docker-mylar3  

Access via Caddy at **https://mylar3.yourdomain.com** (or your configured hostname).

## Quick start

1. Copy `stack.env.example` → `stack.env` (optional: set `PUID`, `PGID`, `TZ`).
2. Ensure the **usenet** and **torrents** networks exist (same as Sonarr/Radarr). Create them if needed: `docker network create usenet` and `docker network create torrents`. For external networks/volumes and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
3. From the stack directory: `docker compose up -d`.
4. In the web UI: add download clients (NZBGet at `nzbget:6789`, qBittorrent at `qbittorrent:8080`), add indexers (Prowlarr or NZBHydra2), then add series and set the comics path to `/comics`.

**Portainer:** Add stack → paste `docker-compose.yml` → set env vars → deploy. Ensure usenet and torrents networks exist.

## Integration with Komga

Point Mylar3’s “Comic location” (or post-processing destination) at `/comics`. To have Komga read the same files, either:

- Use the same named volume in both stacks (e.g. share `mylar3_comics` with Komga by making it external and attaching it to Komga), or  
- Bind-mount a host path to `/comics` in this stack and to Komga’s library path so both see the same directory.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `mylar3:8090`) |
| **Networks** | `monitor` (Caddy), `usenet`, `torrents` (download clients) |
| **Images** | `lscr.io/linuxserver/mylar3:latest` |
| **Storage** | Named volumes: `mylar3_config`, `mylar3_comics`, `mylar3_downloads`; or bind-mount for comics/downloads |

## Caddy reverse proxy

Add a site block for the Mylar3 hostname (e.g. `mylar3.yourdomain.com`):

```
mylar3.yourdomain.com {
	reverse_proxy mylar3:8090
}
```

## Health and monitoring

Mylar3 does not expose a dedicated health endpoint. Use a generic HTTP check to the app URL (e.g. `https://mylar3.yourdomain.com`) in Uptime Kuma.
