# Homarr – homelab dashboard

[Homarr](https://homarr.dev/) is a dashboard for your homelab: add links to your services, widgets (Docker, Uptime Kuma, etc.), and optional integrations. This stack runs Homarr behind Caddy. No host ports; access via Caddy.

**Website:** https://homarr.dev/  
**Docs:** https://homarr.dev/docs/  
**GitHub:** https://github.com/ajnart/homarr  
**Docker image:** https://github.com/ajnart/homarr/pkgs/container/homarr  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Optionally set `TZ`.
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Homarr listens on port `7575` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://homarr.yourdomain.com` → `homarr:7575`
   - Add your apps and widgets in the UI (drag-and-drop).

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `homarr:7575`)                                   |
| **Network** | `monitor` (for Caddy) + default                                             |
| **Images**  | `ghcr.io/ajnart/homarr:latest`                                               |
| **Storage** | `homarr_config` (configs), `homarr_data`; Docker socket for optional integrations |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `homarr.yourdomain.com` → `homarr:7575` |

## Portainer

Add stack from this directory; ensure `stack.env` exists. No host ports; use Caddy to expose the service.
