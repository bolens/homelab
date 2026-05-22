# CUPS (network print server)

Self-hosted **CUPS** print server with a web admin UI, **IPP** sharing, and common Debian printer drivers. Suitable as a homelab “cloud print” hub: add printers in the UI, then point clients at `ipp://…` or install the queue via your OS print settings.

**Website:** https://www.cups.org  
**Docs:** https://openprinting.github.io/cups/  
**Container image:** https://github.com/anujdatar/cups-docker  
**Docker Hub:** https://hub.docker.com/r/anujdatar/cups  

## Quick start

1. Run `./prepare-stack.sh` (creates `stack.env`, `caddy_snippet.conf`, ensures `monitor` network).
2. Set `CUPSPASSWORD` (and optionally `CUPSADMIN`) in `stack.env`. Generate a password, for example:

   ```bash
   openssl rand -base64 24
   ```

3. If you use **USB printers** on the Docker host, edit `docker-compose.yml` and uncomment the `devices:` block mapping `/dev/bus/usb`.
4. Deploy from this directory:

   ```bash
   docker compose up -d
   ```

5. Copy hostnames in `caddy_snippet.conf` from the `.example` pattern to your real vhost, reload Caddy, then open the admin UI at your HTTPS URL (e.g. `https://cups.example.com`).

## Configuration

| Item | Details |
|------|---------|
| **Port** | 631 (HTTP inside the container; proxied by Caddy) |
| **Network** | `monitor` only — no published host ports |
| **Image** | `anujdatar/cups:latest` |
| **Data** | Docker volume `cups_config` → `/etc/cups` (queues, drivers, `cupsd.conf`) |
| **Auth** | Web admin uses `CUPSADMIN` / `CUPSPASSWORD` from `stack.env` |

## Clients

- **LAN / VPN:** Add an **IPP** printer using `ipp://cups.home:631/printers/<QueueName>` (adjust host and queue name; use your internal DNS name if different).
- **Behind Caddy only:** Use the public or internal HTTPS hostname your Caddyfile serves; some clients prefer `https://cups.example.com:443/printers/...` depending on OS—if redirects or TLS confuse the client, add the printer by hostname that matches what CUPS sees (see upstream CUPS reverse-proxy notes).

**AirPrint / mDNS:** The image includes Avahi, but discovery through Docker bridges is often unreliable. If phones do not see the printer automatically, use **manual IPP URL** or run mDNS/reflector on the host; see upstream issues in [anujdatar/cups-docker](https://github.com/anujdatar/cups-docker).

## Portainer

- **Stacks** → add stack from repo path `stacks/cups/docker-compose.yml`.
- Ensure the stack attaches to external network **`monitor`** so Caddy can reach `cups:631`.
- Set `CUPSPASSWORD` (and optional `CUPSADMIN`) in the stack environment; do not publish `631` on the host if Caddy is the entrypoint.

## Backup

- Back up the Docker volume **`cups_config`** (printer definitions and `cupsd.conf`).
- Re-run `./prepare-stack.sh` only for env/Caddy templates; it does not reset the volume.

## Security

- Treat the CUPS admin UI as **high privilege** (install drivers, change queues). Prefer **Cloudflare Access** (or VPN-only access) on the public hostname; see [ACCESS-SSO.md](../../documents/ACCESS-SSO.md).
- Use a **strong** `CUPSPASSWORD`; the default `password` from upstream is only for first boot before you set `stack.env`.
