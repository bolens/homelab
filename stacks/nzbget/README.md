# NZBGet

High-performance Usenet downloader. NZBGet handles NZB downloads from Usenet providers and integrates with automation tools like Sonarr, Radarr, Lidarr, and Prowlarr.

**Website:** https://nzbget.com/  
**Docs:** https://nzbget.com/documentation  
**GitHub:** https://github.com/nzbgetcom/nzbget  
**Docker image:** https://hub.docker.com/r/linuxserver/nzbget  
**Releases:** https://github.com/nzbgetcom/nzbget/releases  

## Quick start

1. **Shared networks and volumes**
   - Create the shared **usenet** network (once per host, if not already present):
     ```bash
     docker network create usenet
     ```
   - Create the shared **usenet_downloads** volume (used by *arr and other apps):
     ```bash
     docker volume create usenet_downloads
     ```
   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set:
     - `TZ` to your timezone.
     - `PUID` / `PGID` to the user/group that should own downloaded files.
     - Optionally `NZBGET_USER` / `NZBGET_PASS` (web UI credentials).
3. **Deploy**
   - From this directory:
     ```bash
     docker compose up -d
     ```
   - Or add the stack in Portainer, paste the compose, and set the same variables in the stack **Environment**.
4. **First run**
   - Access NZBGet via Caddy (for example `https://nzbget.home` or `https://nzbget.yourdomain.com`) and configure:
     - Your Usenet server(s).
     - Download directory (should be `/downloads` inside the container).
     - Optional post-processing scripts.

This stack uses a **named config volume** (`nzbget_config`) and the shared **`usenet_downloads`** volume so it works well when deployed from Portainer and integrates cleanly with Sonarr/Radarr/Lidarr, etc.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `nzbget:6789`)          |
| **Networks** | `monitor` (for Caddy/monitoring) and `usenet` (shared usenet network) |
| **Image**  | `lscr.io/linuxserver/nzbget:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`, optional `UMASK`, `NZBGET_USER`, `NZBGET_PASS`   |
| **Storage**| `nzbget_config` → `/config`, `usenet_downloads` → `/downloads`         |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
nzbget.home, nzbget.local {
  tls internal
  reverse_proxy nzbget:6789
}
```

For public access via Cloudflare Tunnel, add a corresponding `nzbget.yourdomain.com` block in your Caddyfile and Zero Trust Access app if you want SSO in front of the NZBGet UI.

## Integration with *arr and Prowlarr

- **Download client:** In Sonarr/Radarr/Lidarr/Readarr, add NZBGet as a download client:
  - Host: `nzbget`
  - Port: `6789`
  - URL base: (empty, unless you change it in NZBGet)
  - Category: set per-app (e.g. `tv`, `movies`, `music`, `books`) and configure NZBGet categories accordingly.
- **Path mapping:** Use `/downloads` as the download root in NZBGet and in your *arr apps so they see the same files via the shared `usenet_downloads` volume.

