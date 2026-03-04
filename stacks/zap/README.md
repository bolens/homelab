# OWASP ZAP (Zed Attack Proxy)

Web application and API security scanner: run baseline scans, active scans, and manual exploration against your homelab apps. [OWASP ZAP](https://www.zaproxy.org/) runs in daemon mode with a web UI—no host ports; access via Caddy.

**Website:** https://www.zaproxy.org/  
**Docs:** https://www.zaproxy.org/docs/  
**GitHub:** https://github.com/zaproxy/zaproxy  
**Docker image:** https://github.com/zaproxy/zaproxy/pkgs/container/zaproxy  
**Releases:** https://github.com/zaproxy/zaproxy/releases  

## Quick start

1. **Start the stack**

   ```bash
   docker compose up -d
   ```

2. **Access the UI**

   Open your Caddy hostname (e.g. `https://zap.home`). Use the ZAP UI to:
   - Enter a URL and run an **Automated Scan** (baseline or full).
   - Use **Manual Explore** (browser launcher) for interactive testing.
   - Configure **API** scans for your internal services.

3. **Scanning internal hosts**

   From inside the ZAP container, other stacks on the `monitor` network are reachable by service name (e.g. `http://simplelogin:7777`, `http://paperless-ngx:8000`). Use those URLs in ZAP when scanning apps that are not exposed by hostname.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (reverse proxy to `zap:8090`). No host ports. |
| **Network** | `monitor` (external). Caddy must be on the same network. |
| **Image** | `ghcr.io/zaproxy/zaproxy:stable` (official). |
| **Persistence** | By default none; ZAP config/sessions are lost on restart. To persist, uncomment the `volumes` block in `docker-compose.yml` and create volume `zap-data`. |

## Caddy reverse proxy

Example Caddy vhost (main `stacks/caddy` Caddyfile):

```caddyfile
zap.home, zap.local {
	tls internal
	reverse_proxy zap:8090
}
```

With Cloudflare Tunnel host routing, add a handle for your public hostname (e.g. `zap.yourdomain.com`) and `reverse_proxy zap:8090`.

## Rebuild / update

```bash
docker compose pull zap
docker compose up -d
```
