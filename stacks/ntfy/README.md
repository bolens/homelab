# ntfy – push notifications

[ntfy](https://ntfy.sh/) is a simple HTTP-based pub-sub notification service. Send push notifications via PUT/POST; use the Android/iOS app or curl to subscribe. This stack runs ntfy behind Caddy. No host ports; access via Caddy.

**Website:** https://ntfy.sh/  
**Docs:** https://docs.ntfy.sh/  
**GitHub:** https://github.com/binwiederhier/ntfy  
**Docker image:** https://hub.docker.com/r/binwiederhier/ntfy  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set `NTFY_BASE_URL` to your Caddy hostname (e.g. `https://ntfy.yourdomain.com`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - ntfy listens on port `80` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://ntfy.yourdomain.com` → `ntfy:80`
   - Publish: `curl -d "message" https://ntfy.yourdomain.com/mytopic`
   - Subscribe: `curl -s https://ntfy.yourdomain.com/mytopic` or use the ntfy app with your server URL.

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `ntfy:80`)                                      |
| **Network** | `monitor` (for Caddy) + default                                             |
| **Images**  | `binwiederhier/ntfy:latest`                                                 |
| **Storage** | `ntfy_cache`, `ntfy_config` (optional server.yml)                           |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `ntfy.yourdomain.com` → `ntfy:80` |

**Alertmanager:** To receive Prometheus alerts on your phone, deploy **stacks/alertmanager** on the `monitor` network; the example config sends alerts to `http://ntfy:80/alerts`. Subscribe to the topic `alerts` in the ntfy app (or set the topic in `alertmanager.yml` and subscribe to that). See the main [docker README](../../README.md) step-by-step for the full monitoring stack.

For auth, upstream limits, and Firebase (mobile), see [ntfy config](https://docs.ntfy.sh/config/). Optional: put a `server.yml` in the config volume and reference it.

## Portainer

Add stack from this directory; set `NTFY_BASE_URL` in stack env. No host ports; use Caddy to expose the service.
