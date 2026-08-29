# Plex

Self-hosted media server for movies, TV shows, and music. Plex serves your media library to web, mobile, TV apps, and other clients.

**Website:** https://www.plex.tv/  
**Docs:** https://support.plex.tv/  
**Docker image:** https://hub.docker.com/r/linuxserver/plex  
**Releases:** https://support.plex.tv/articles/205165398-plex-media-server-release-notes/  

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set:
     - `TZ` to your timezone.
     - `PUID` / `PGID` to the user/group that should own media and metadata.
     - Confirm media paths (defaults `/mnt/unraid/media/{tv,movies,music}`).
     - Keep `PLEX_VERSION=latest` to install the newest release available to
       the signed-in account, or use `public` to avoid Plex Pass beta releases.
     - Optionally `PLEX_CLAIM` with a claim token from Plex (first run only).
2. **Deploy**
   - From this directory:
     ```bash
     docker compose up -d
     ```
3. **First run**
   - Browse to `http://<docker-host>:32400/web` and complete the Plex setup.
   - Add libraries pointing to:
     - `/data/tv` for TV shows.
     - `/data/movies` for movies.
     - `/data/music` for music.

Media libraries are bind-mounted from the same host paths used by Sonarr/Radarr/Lidarr (defaults under `/mnt/unraid/media/`).
An idempotent startup hook ensures the named `/transcode` volume remains
writable by the configured `PUID`/`PGID`.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Direct via `http://host:32400/web`, or via Caddy reverse proxy         |
| **Network**| Plex uses host networking for direct clients and LAN discovery; a port-32400-only proxy preserves segmented `ingress-public` and `media-services` access |
| **Image**  | `lscr.io/linuxserver/plex:latest`                                      |
| **Env**    | `TZ`, `PUID`, `PGID`, `PLEX_VERSION`, `PLEX_*_PATH`, optional `PLEX_CLAIM` |
| **Storage**| `plex_config` → `/config`, `plex_transcode` → `/transcode`, host media paths → `/data/{tv,movies,music}` |

## Direct connections and Remote Access

Plex displays **Indirect** or **Not connected directly** when the client has
fallen back to Plex Relay. This stack uses host networking so Plex advertises
the Docker host's LAN address instead of an unreachable container address.
Host networking exposes Plex's listeners directly on every host interface, so
the host firewall and router rules are security-critical.

The `plex-network-proxy` sidecar exposes only Plex HTTP port `32400` to the
`ingress-public` and `media-services` Docker networks under the network alias
`plex`. Caddy, Kometa, Tautulli, and other trusted integrations can therefore
continue using `http://plex:32400` without attaching the host-networked Plex
process to those bridge networks.

For remote clients:

1. Give the Docker host a DHCP reservation or static LAN address.
2. Forward `PLEX_REMOTE_PORT` **TCP** on the router to port `32400` TCP at that
   host address. Do not forward the UDP discovery or companion ports to the
   internet; restrict those ports to the LAN in the host firewall.
3. In Plex Web, open **Settings > Server > Remote Access**, enable
   **Manually specify public port**, enter the value of `PLEX_REMOTE_PORT`, and
   select **Apply** or **Retry**. The public and private connection indicators
   should both turn green.
4. Allow the same TCP port through the host firewall, if one is enabled.
5. Test from outside the LAN, such as a phone with Wi-Fi disabled. A test from
   inside the LAN also requires router hairpin NAT or split-horizon DNS.

If this still fails, check whether the router's WAN address differs from the
public address reported by the ISP. That normally indicates double NAT or
carrier-grade NAT (CGNAT). Forward the port on both routers, bridge the upstream
router, or request a public IPv4 address from the ISP. An inbound VPN is the
safer alternative when no public address is available.

For local clients, keep **Enable local network discovery (GDM)** enabled under
**Settings > Server > Network** and leave **Secure connections** at Plex's
recommended **Preferred** setting. Host networking lets GDM announce the
server directly on the LAN. Do not add LAN
ranges to **List of IP addresses and networks that are allowed without auth**;
that setting grants unauthenticated clients owner-level access.

To verify playback, open the Plex Dashboard while streaming and inspect the
session. It should say **Local** or **Remote** and **Direct Play** (or direct
stream/transcode when the media requires it), not **Indirect**. Set **Internet
upload speed** to the measured upstream rate; Plex reserves part of that value
for non-streaming traffic. Keep transcoder quality at **Automatic** and enable
hardware acceleration only when the host has a supported GPU and Plex Pass.

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
plex.home, plex.local {
  tls internal
  reverse_proxy host.docker.internal:32400
}
```

Caddy is useful for the browser UI, but Plex apps should use Plex's native
direct TCP Remote Access path above. Do not put media traffic through a
Cloudflare Tunnel or Cloudflare Access: Access authentication is not understood
by Plex clients and a tunnel does not make Plex Remote Access direct. If a
custom reverse-proxy URL is deliberately used, add its HTTPS URL under
**Settings > Server > Network > Custom server access URLs** and preserve the
headers shown in `caddy_snippet.conf.example`.

The Caddy example contains placeholder names. Replace them in the local,
ignored Caddy snippet; never commit a real hostname or API token.
