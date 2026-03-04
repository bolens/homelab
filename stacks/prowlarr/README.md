# Prowlarr

Indexer manager and proxy for Usenet and torrents. Prowlarr manages indexers centrally and syncs them to Sonarr, Radarr, Lidarr, Readarr, and other *arr apps.

**Website:** https://prowlarr.com/  
**Docs:** https://wiki.servarr.com/prowlarr  
**GitHub:** https://github.com/Prowlarr/Prowlarr  
**Docker image:** https://hub.docker.com/r/linuxserver/prowlarr  
**Releases:** https://github.com/Prowlarr/Prowlarr/releases  

## Quick start

1. **Shared networks** (if not already created):
   ```bash
   docker network create usenet
   docker network create torrents
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
   - Access Prowlarr via Caddy (for example `https://prowlarr.home` or `https://prowlarr.yourdomain.com`).
   - Add your Usenet and torrent indexers (Newznab/Torznab).
   - Configure app sync for Sonarr/Radarr/Lidarr/Readarr.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `prowlarr:9696`)        |
| **Networks** | `monitor`, `usenet`, `torrents`, plus default                         |
| **Image**  | `lscr.io/linuxserver/prowlarr:latest`                                  |
| **Env**    | `TZ`, `PUID`, `PGID`                                                   |
| **Storage**| `prowlarr_config` → `/config`                                          |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
prowlarr.home, prowlarr.local {
  tls internal
  reverse_proxy prowlarr:9696
}
```

