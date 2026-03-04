# WireGuard server (LinuxServer.io)

Remote access VPN server so you can connect laptops and phones into your homelab over WireGuard. This stack runs the LinuxServer.io WireGuard image and exposes **UDP 51820** on the host. No HTTP UI; peer configs and QR codes are generated under the `wireguard_config` volume.

**Docs:** https://docs.linuxserver.io/images/docker-wireguard/  
**GitHub:** https://github.com/linuxserver/docker-wireguard  

## Stack type

- **No Caddy hostname** – WireGuard is UDP-only; clients connect directly to your host’s public IP or domain on port 51820.
- **Host port** – Only `51820/udp` is bound (required for VPN; not HTTP).

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, `PGID`, `SERVERURL` (your public IP or DNS, or `auto`), `SERVERPORT` (default 51820), and `PEERS` (number or comma-separated names).

2. **Deploy**
   From this directory:
   ```bash
   docker compose up -d
   ```

3. **Port forwarding**
   On your router, forward **UDP** port 51820 (or your `SERVERPORT`) to the Docker host.

4. **Peer configs**
   The container writes peer configs into the `wireguard_config` volume. Use `docker exec wireguard /app/show-peer 1` (and peer index) to print configs or QR codes, or browse the volume from the host. Import into WireGuard clients on your devices.

## Configuration

| Item | Details |
|------|---------|
| **Access** | UDP 51820 only; no HTTP. |
| **Ports** | `51820:51820/udp` on the host (forward on router). |
| **Env** | `TZ`, `PUID`, `PGID`; `SERVERURL`, `SERVERPORT`, `PEERS`; optional `PEERDNS`, `INTERNAL_SUBNET`, `ALLOWEDIPS`, `PERSISTENTKEEPALIVE_PEERS`. See LinuxServer docs. |
| **Storage** | `wireguard_config` → `/config` (server and peer configs). |

## Portainer

Add stack from this directory, paste the compose, set env vars in the stack **Environment**, then deploy. Ensure the host has the WireGuard kernel module (see LinuxServer docs).
