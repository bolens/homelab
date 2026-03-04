# Gluetun – VPN client for other containers

Outbound VPN client so **specific containers** can use a commercial VPN without putting the whole host behind it. Other stacks attach with `network_mode: service:gluetun` (e.g. the qbittorrent stack uses its own Gluetun instance; this stack is for a shared or alternate VPN client).

**Docs:** https://gluetun.com/  
**GitHub:** https://github.com/qdm12/gluetun  
**Provider wiki:** https://github.com/qdm12/gluetun-wiki  

## Stack type

- **No Caddy hostname** – this stack has no HTTP service; it is a VPN tunnel only.
- **No host ports** – other containers reach it via `network_mode: service:gluetun`.

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `VPN_SERVICE_PROVIDER`, `VPN_TYPE`, and provider-specific vars (see [Gluetun configuration](https://gluetun.com/configuration/) and the [provider wiki](https://github.com/qdm12/gluetun-wiki)).

2. **Deploy**
   From this directory:
   ```bash
   docker compose up -d
   ```

3. **Route another container through Gluetun**
   In another stack’s `docker-compose.yml`, set:
   ```yaml
   my-service:
     image: your/image
     network_mode: service:gluetun
     depends_on:
       - gluetun
   ```
   (That stack must be deployed in the same compose project as gluetun, or use the gluetun container name from the host.)

## Configuration

| Item | Details |
|------|---------|
| **Access** | No HTTP; container is used via `network_mode: service:gluetun`. |
| **Env** | `TZ`; `VPN_SERVICE_PROVIDER`, `VPN_TYPE`; provider-specific (e.g. WireGuard keys or OpenVPN user/pass). See `stack.env.example` and Gluetun wiki. |
| **Storage** | `gluetun_config` → `/gluetun` (server lists, optional custom config). |

## Portainer

Add stack from this directory, paste the compose, set env vars in the stack **Environment**, then deploy.
