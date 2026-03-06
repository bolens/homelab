# qBittorrent + VPN (Gluetun)

Torrent client with **all traffic routed through a VPN** (Gluetun). Intended for **automated torrents** from Sonarr/Radarr/Lidarr/Readarr. The stack uses the shared `torrents` network and `torrents_downloads` volume so *arr apps can send torrents to qBittorrent and read completed files.

**Website (qBittorrent):** https://www.qbittorrent.org/  
**Docs (Gluetun):** https://gluetun.com/  
**Gluetun GitHub:** https://github.com/qdm12/gluetun  
**Gluetun wiki (providers):** https://github.com/qdm12/gluetun-wiki  

## Hostname and access

- **Primary hostname:** `qbittorrent.yourdomain.com` (via Caddy; no host port for the Web UI).
- **Internal URL for *arr stacks:** `http://qbittorrent:8080` (container name `qbittorrent` is the Gluetun container exposing qBittorrent’s Web UI and API).

## Quick start

1. **Shared network and volume** (once per host, if not already present):

   ```bash
   docker network create torrents
   docker volume create torrents_downloads
   ```

   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

2. **Environment**

   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, `PGID`.
   - Configure Gluetun VPN: set `VPN_SERVICE_PROVIDER` and provider-specific variables (e.g. custom WireGuard keys, or Mullvad/NordVPN/ProtonVPN env vars). See [Gluetun configuration](https://gluetun.com/configuration/) and the [provider wiki](https://github.com/qdm12/gluetun-wiki).

3. **Deploy**

   From this directory:

   ```bash
   docker compose up -d
   ```

4. **First run**

   - Access the qBittorrent Web UI via Caddy (e.g. `https://qbittorrent.yourdomain.com`). Default login is `admin` / `adminadmin`; change it in the UI.
   - In Sonarr/Radarr/Lidarr/Readarr, add a download client: **qBittorrent**, host `qbittorrent`, port `8080`, and the credentials you set.
   - Set the torrent listening port in qBittorrent. For incoming peers, use your VPN provider’s port forwarding (configure in Gluetun; see Gluetun docs). No host port binding is used; Caddy handles all HTTP access to the Web UI.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Web UI and API on port 8080 inside the stack; **only via Caddy** (no host ports). |
| **Networks** | `torrents` (for *arr and peers), `monitor` (for Caddy). |
| **Ports** | No host port bindings. Torrent listening port 6881 is internal; for incoming peers use your VPN provider’s port forwarding in Gluetun and set that port in qBittorrent’s connection settings. |
| **Env** | `TZ`, `PUID`, `PGID`; Gluetun: `VPN_SERVICE_PROVIDER`, `VPN_TYPE`, and provider-specific vars (see `stack.env.example` and Gluetun docs). |
| **Storage** | `qbittorrent_config` → qBittorrent config; `torrents_downloads` (external) → completed downloads for *arr. |

## Caddy reverse proxy

Add a site block for the Web UI (example with internal TLS):

```caddyfile
qbittorrent.yourdomain.com {
  tls internal
  reverse_proxy qbittorrent:8080
}
```

## How this fits with rtorrent-flood

- **Automated torrents** (Sonarr/Radarr/Lidarr/Readarr) use this **qBittorrent+VPN** stack on the `torrents` network and the shared volume `torrents_downloads`.
- **Manual / private-tracker torrents** can use the **rtorrent-flood** stack with `torrents_manual`, so automated and manual traffic stay separate.
