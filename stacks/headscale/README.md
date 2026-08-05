# Headscale

Self-hosted implementation of the Tailscale control server. Lets you run your own Tailscale-style mesh VPN and use Tailscale clients (or headscale-specific options) to connect.

**Website:** https://headscale.net  
**Docs:** https://headscale.net/docs/  
**GitHub:** https://github.com/juanfont/headscale  
**Docker image:** https://hub.docker.com/r/headscale/headscale  
**Releases:** https://github.com/juanfont/headscale/releases  

## Quick start

1. **Prepare and edit config**
   - Run `./prepare-stack.sh`. It creates `stack.env`, the configured
     `HEADSCALE_CONFIG_PATH`, and the Caddy snippet without overwriting them.
   - Edit the generated config and set at least:
     - `server_url`: public URL (e.g. `https://headscale.yourdomain.com`) — required for clients.
     - `dns.base_domain`: a domain you control for MagicDNS (e.g. `ts.yourdomain.com`).
2. **Deploy**
   - **Portainer:** Set `HEADSCALE_CONFIG_PATH` to the absolute host path of the
     generated config and ensure that path is available to the Docker host.
   - **CLI:** From the stack directory:
     ```bash
     docker compose up -d
     ```
   - To change config later: edit the file at `HEADSCALE_CONFIG_PATH` and
     recreate the container.
3. **Caddy:** Reverse-proxy your Headscale hostname to `http://headscale:8080`.
4. **First use:** Create a user and pre-auth keys; see [Getting started](https://headscale.net/stable/usage/getting-started/).

The config is bind-mounted read-only. Headscale state remains in the
`headscale_data` named volume.

## Configuration

| Item | Details |
|------|---------|
| **Ports** | 8080 (API/HTTP), 9090 (metrics). Proxied via Caddy; host ports for direct access if needed. |
| **Network** | `proxy-ingress` for Caddy; `observability` for Prometheus metrics |
| **Image** | headscale/headscale (Docker Hub) |
| **Config** | Bind-mounted from `HEADSCALE_CONFIG_PATH` to `/etc/headscale/config.yaml` (read-only). |
| **Storage** | Config bind mount plus `headscale_data` named volume for DB and keys |

## CLI

Use the Headscale CLI (install separately) and point it at your server URL, or run commands inside the container, e.g.:

```bash
docker exec headscale headscale users list
docker exec headscale headscale preauthkeys create --user myuser --reusable
```
