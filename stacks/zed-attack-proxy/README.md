# OWASP ZAP (Zed Attack Proxy)

Web application and API security scanner. This stack runs ZAP with the **Webswing UI and proxy**; access it through your browser or via ZAP desktop/scripts pointing at the proxy port via Caddy.

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

2. **Web UI and proxy**

   - **Web UI:** open `https://zap.home/zap` (or `https://zap.local/zap`) in your browser to load the ZAP desktop UI via Webswing.  
   - **Proxy/API:** configure ZAP desktop or tools to use `zap.home:8080` / `zap.local:8080` as the ZAP proxy.

3. **Scanning internal hosts**

   From inside the ZAP container, other stacks on the `ingress-admin` network are reachable by service name (e.g. `http://simplelogin:7777`, `http://paperless-ngx:8000`). Use those URLs in ZAP when scanning apps that are not exposed by hostname.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (reverse proxy to `zap:8080`). No host ports. |
| **Networks** | `security-research` for research targets; `ingress-admin` for Caddy access. |
| **Image** | `ghcr.io/zaproxy/zaproxy:stable` (official). |
| **Persistence** | By default none; ZAP config/sessions are lost on restart. To persist, uncomment the `volumes` block in `docker-compose.yml` and create volume `zap-data`. |

## Caddy reverse proxy

Example Caddy vhost (main `stacks/caddy` Caddyfile):

```caddyfile
zap.home, zap.local {
	tls internal
	reverse_proxy zap:8080
}
```

With Cloudflare Tunnel host routing, add a handle for your public hostname (e.g. `zap.example.com`) and `reverse_proxy zap:8080`.

## Rebuild / update

```bash
docker compose pull zap
docker compose up -d
```
