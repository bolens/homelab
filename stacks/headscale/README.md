# Headscale

Self-hosted implementation of the Tailscale control server. Lets you run your own Tailscale-style mesh VPN and use Tailscale clients (or headscale-specific options) to connect.

**Website:** https://headscale.net  
**GitHub:** https://github.com/juanfont/headscale

## Quick start

1. **Config**
   - Copy `config.example.yaml` to `config.yaml` and set at least:
     - `server_url`: public URL (e.g. `https://headscale.yourdomain.com`) — required for clients.
     - `dns.base_domain`: a domain you control for MagicDNS (e.g. `ts.yourdomain.com`).
2. **Deploy**
   - **Portainer:** Encode your config and set it as a stack env var:
     - Generate base64: `base64 -w 0 config.yaml` (Linux) or `base64 -i config.yaml | tr -d '\n'` (macOS).
     - In the stack, add environment variable `HEADSCALE_CONFIG_B64` and paste the base64 string.
     - Deploy the stack. An init container writes the config into the volume; Headscale starts after it.
   - **CLI:** In the stack directory, set `HEADSCALE_CONFIG_B64` in `.env` (paste the base64 output), then:
     ```bash
     docker compose up -d
     ```
   - To change config later: update `config.yaml`, regenerate base64, set `HEADSCALE_CONFIG_B64`, and redeploy (the init container overwrites the volume on each deploy).
3. **Caddy:** Reverse-proxy your Headscale hostname to `http://headscale:8080`.
4. **First use:** Create a user and pre-auth keys; see [Getting started](https://headscale.net/stable/usage/getting-started/).

The stack uses an **init container** to write config from `HEADSCALE_CONFIG_B64` into the `headscale_config` volume, so Portainer (and CLI) only need that one env var—no one-off copy step.

## Configuration

| Item | Details |
|------|---------|
| **Ports** | 8080 (API/HTTP), 9090 (metrics). Proxied via Caddy; host ports for direct access if needed. |
| **Network** | `monitor` (external) — Caddy can reverse-proxy to `headscale:8080` |
| **Image** | headscale/headscale (Docker Hub) |
| **Config** | Set `HEADSCALE_CONFIG_B64` to the base64-encoded contents of your `config.yaml` (see Quick start). |
| **Storage** | Named volumes: `headscale_config` (written by init, read-only in Headscale), `headscale_data` (DB, keys) |

## Optional: bind mount for config (CLI only)

If you prefer to edit config on the host and don’t need Portainer deploy, you can remove the init container and use a bind mount. In `docker-compose.yml`: delete the `headscale-init` service, remove `depends_on` from `headscale`, and replace the config volume with:

```yaml
volumes:
  - ./config:/etc/headscale:ro
  - headscale_data:/var/lib/headscale
```

Put your `config.yaml` in `./config/`. This does not work when deploying from Portainer’s web editor (no host path).

## CLI

Use the Headscale CLI (install separately) and point it at your server URL, or run commands inside the container, e.g.:

```bash
docker exec headscale headscale users list
docker exec headscale headscale preauthkeys create --user myuser --reusable
```
