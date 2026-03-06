# rTorrent + Flood (manual torrents)

Manual torrent stack for **hand‑curated torrents from private trackers**. Uses the LinuxServer.io `rtorrent-flood` image, which bundles the rTorrent daemon with the Flood web UI.

**Website:** https://github.com/jesec/flood  
**Docs:** https://github.com/jesec/flood/wiki  
**GitHub:** https://github.com/jesec/flood  
**Docker image:** https://hub.docker.com/r/linuxserver/rtorrent-flood  
**Releases:** https://github.com/jesec/flood/releases  

## Quick start

1. **Shared networks and volumes** (once per host, if not already present):

   ```bash
   docker network create --driver bridge --subnet 172.30.11.0/24 torrents
   docker volume create torrents_manual
   ```

   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

2. **Environment**

   - Copy `stack.env.example` to `stack.env`.
   - Set:
     - `TZ` to your timezone.
     - `PUID` / `PGID` to the user/group that should own the downloaded files.

3. **Deploy**

   From this directory:

   ```bash
   docker compose up -d
   ```

4. **First run**

   - Access Flood via Caddy (see example below) or temporarily via `http://<docker-host>:3000` if you bind that port.
   - Configure:
     - Download directory inside the container as `/downloads`.
     - Your private trackers, rTorrent settings, and labels/categories as preferred.

This stack is intended for **manual use only**. Keep your *arr automation stacks (Sonarr/Radarr/Lidarr/Readarr) pointed at the qBittorrent+VPN stack instead, so manual and automated torrents stay logically separated.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Flood web UI on port 3000 inside the container; proxied via Caddy      |
| **Networks** | `torrents` (for torrent traffic) and `monitor` (for Caddy/Flood UI)   |
| **Ports**  | `49160/tcp` and `49160/udp` forwarded from host for incoming peers     |
| **Env**    | `TZ`, `PUID`, `PGID`, optional `UMASK`                                 |
| **Storage**| `rtorrent_flood_config` → `/config`, `torrents_manual` → `/downloads`  |

### Notes on ports and port‑forwarding

- This stack exposes rTorrent’s listening port `49160` on the Docker host.
- If you want incoming connections from the Internet (often required by private trackers), forward that port on your router to the Docker host.
- You can change the host port in `docker-compose.yml` if you prefer a different external port; keep the container ports at `49160`.

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
rtorrent.home, rtorrent.local {
  tls internal
  reverse_proxy rtorrent-flood:3000
}
```

For public access (if desired), add e.g. `rtorrent.yourdomain.com` in the public HTTPS section of your Caddyfile and consider protecting it with Cloudflare Access or other SSO.

## How this fits with qBittorrent+VPN

- **Automated torrents** (Sonarr/Radarr/Lidarr/Readarr) should use **qBittorrent+VPN** on the `torrents` network and a shared volume like `torrents_downloads`.
- **Manual / private‑tracker torrents** live in this stack, using `torrents_manual`.
- Keeping them separate lets you:
  - Apply a VPN and strict rules to the automated client.
  - Keep curated private‑tracker torrents under separate control and paths.

