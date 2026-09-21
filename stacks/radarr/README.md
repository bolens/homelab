# Radarr

Movie collection manager for Usenet and torrents. Radarr monitors your wanted movies, grabs releases from NZB/torrent indexers, sends them to download clients, and organizes the resulting files.

**Website:** https://radarr.video/  
**Docs:** https://wiki.servarr.com/radarr  
**GitHub:** https://github.com/Radarr/Radarr  
**Docker image:** https://hub.docker.com/r/linuxserver/radarr  
**Releases:** https://github.com/Radarr/Radarr/releases  

## Quick start

1. **Shared networks and torrent download volume** (if not already created):
   ```bash
   docker network create usenet
   docker network create torrents
   mkdir -p /mnt/unraid/media/movies /mnt/unraid/media/downloads/{usenet,torrents}
   ```
   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, and `PGID`.
   - Confirm `RADARR_MEDIA_PATH` (default `/mnt/unraid/media`).
3. **Deploy**
   - From this directory:
     ```bash
     docker compose --env-file stack.env up -d
     ```
4. **First run**
   - Access Radarr via Caddy (for example `https://radarr.home` or `https://radarr.yourdomain.com`).
   - Configure:
     - **Download client**: NZBGet (`http://nzbget:6789`) and/or qBittorrent (`http://qbittorrent:8080`).
     - **Indexers**: from Prowlarr/NZBHydra 2.
     - **Root folder**: `/data/movies`.
     - **NZBGet remote path mapping**: host `nzbget`, remote
       `/downloads/`, local `/data/downloads/usenet/`.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `radarr:7878`)          |
| **Networks** | `ingress-admin`, `usenet`, `torrents`, plus default                         |
| **Image**  | `lscr.io/linuxserver/radarr:6.4.4.10685-ls318`, pinned by digest in Compose |
| **Memory** | 6 GiB RAM limit; 8 GiB combined RAM and swap limit, if host swap is available |
| **Env**    | `TZ`, `PUID`, `PGID`, `RADARR_MEDIA_PATH`, optional `RADARR__*` |
| **Storage**| `radarr_config` → `/config`, `${RADARR_MEDIA_PATH}` → `/data`; use `/data/movies` and `/data/downloads/*` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
radarr.home, radarr.local {
  tls internal
  reverse_proxy radarr:7878
}
```

## Media preparation prerequisite

Verify the configured media directories exist on the intended filesystem before
running preparation. The helper refuses to create missing media paths. Directory
existence alone does not verify the remote mount; check its source and access.

## Upgrade and recovery

Before upgrading, create and verify a Radarr backup under **System → Backup** and
keep a copy outside the container. Record the previous image digest. Upgrade the
container image rather than using Radarr's in-app updater:

```bash
docker compose --env-file stack.env pull radarr
docker compose --env-file stack.env up -d --no-deps radarr
```

Verify the version under **System → Status**, container health, and loading the
full movie list. If rollback is needed after a database migration, restore the
matching pre-upgrade backup with the previous image. Reverting the image alone
may not be compatible with an upgraded database.

## Memory errors

`System.OutOfMemoryException` can fail movie-list requests while the container
still reports healthy. Check `docker stats --no-stream radarr`, the exception
stack trace, and container memory-pressure counters. `OOMKilled=false` does not
rule out an application allocation failure.

The 6 GiB RAM limit provides more headroom for movie-list processing than the
previous 3 GiB limit. The 8 GiB combined limit permits up to 2 GiB of swap. Ensure
the host has capacity before deployment. This is a memory-pressure mitigation,
not proof that an application memory leak or oversized allocation is fixed.
After upgrading, repeat the failing movie-list request and check for new
exceptions. If it still fails, retain a sanitized stack trace and measure memory
during the request before increasing limits again.
