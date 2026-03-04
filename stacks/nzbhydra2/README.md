# NZBHydra 2

Meta search for Usenet indexers. NZBHydra 2 aggregates results from multiple NZB indexers, normalizes them, and exposes a Newznab-compatible API for apps like Sonarr, Radarr, Lidarr, and Prowlarr.

**Docs:** https://github.com/theotherp/nzbhydra2/wiki  
**GitHub:** https://github.com/theotherp/nzbhydra2  
**Docker image:** https://hub.docker.com/r/linuxserver/nzbhydra2  
**Releases:** https://github.com/theotherp/nzbhydra2/releases  

## Quick start

1. **Shared network**
   - Ensure the shared **usenet** network exists (once per host):
     ```bash
     docker network create usenet
     ```
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, and `PGID` as appropriate for your host.
3. **Deploy**
   - From this directory:
     ```bash
     docker compose up -d
     ```
   - Or add the stack in Portainer and set the same variables in the stack **Environment**.
4. **First run**
   - Access NZBHydra 2 via Caddy (for example `https://nzbhydra.home` or `https://nzbhydra.yourdomain.com`).
   - Complete the initial wizard:
     - Add your Usenet indexers (Newznab, etc.).
     - Set the base URL and API key.

Config is stored in the `nzbhydra2_config` named volume so it survives container upgrades and works from Portainer’s web editor.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `nzbhydra2:5076`)       |
| **Networks** | `monitor` (for Caddy/monitoring) and `usenet` (shared usenet network) |
| **Image**  | `lscr.io/linuxserver/nzbhydra2:latest`                                 |
| **Env**    | `TZ`, `PUID`, `PGID`, optional `UMASK`                                 |
| **Storage**| `nzbhydra2_config` → `/config`                                         |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
nzbhydra.home, nzbhydra.local {
  tls internal
  reverse_proxy nzbhydra2:5076
}
```

Add a corresponding `nzbhydra.yourdomain.com` block in the public HTTPS section of your Caddyfile if you want to expose it via Cloudflare Tunnel (ideally protected by Cloudflare Access).

## Integration with *arr and Prowlarr

- **Indexer source:** In Sonarr/Radarr/Lidarr/Readarr and Prowlarr, add NZBHydra 2 as a Newznab-compatible indexer:
  - URL: `http://nzbhydra2:5076`
  - API key: from the NZBHydra 2 UI.
  - Categories: TV, Movies, Music, Books, etc., depending on the app.
- **Indexers upstream:** Configure all your Usenet indexers once in NZBHydra 2 and point Prowlarr (and/or the *arr apps directly) at NZBHydra 2 so you get unified search, history, and statistics.

