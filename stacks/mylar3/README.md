# Mylar3

Automated comic book downloader (CBR/CBZ) for Usenet and torrents. Tracks
series, fetches new issues via NZBGet or qBittorrent, and organizes them into
`/data/comics`.

**Homepage:** https://mylarcomics.com  
**GitHub:** https://github.com/mylar3/mylar3  
**Docker (LinuxServer):** https://docs.linuxserver.io/images/docker-mylar3  

Access via Caddy at **https://mylar3.yourdomain.com** (or your configured hostname).

## Quick start

1. Copy `stack.env.example` → `stack.env` (optional: set `PUID`, `PGID`, `TZ`).
2. Confirm `MYLAR3_MEDIA_PATH` (default `/mnt/unraid/media`).
3. Ensure the **usenet** and **torrents** networks exist (same as Sonarr/Radarr). Create them if needed: `docker network create usenet` and `docker network create torrents`. For external networks/volumes and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
4. From the stack directory: `docker compose --env-file stack.env up -d`.
5. In the web UI: add download clients (NZBGet at `nzbget:6789`,
   qBittorrent at `qbittorrent:8080`), add indexers, then set Comic Location
   to `/data/comics`. Set **NZBGet Download Directory** to
   `/data/downloads/usenet/completed/comics`.

**Portainer:** Add stack → paste `docker-compose.yml` → set env vars → deploy. Ensure usenet and torrents networks exist.

## Integration with Komga

Point Mylar3’s Comic Location at `/data/comics`. Komga can continue mounting
the corresponding host directory independently.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `mylar3:8090`) |
| **Networks** | `monitor` (Caddy), `usenet`, `torrents` (download clients) |
| **Images** | `lscr.io/linuxserver/mylar3:latest` |
| **Storage** | `mylar3_config` → `/config`, `${MYLAR3_MEDIA_PATH}` → `/data` |

## Caddy reverse proxy

Add a site block for the Mylar3 hostname (e.g. `mylar3.yourdomain.com`):

```
mylar3.yourdomain.com {
	reverse_proxy mylar3:8090
}
```

## Health and monitoring

Mylar3 does not expose a dedicated health endpoint. Use a generic HTTP check to the app URL (e.g. `https://mylar3.yourdomain.com`) in Uptime Kuma.
