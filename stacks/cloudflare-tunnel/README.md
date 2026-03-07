# Cloudflare Tunnel (cloudflared)

Exposes services on your Docker host via Cloudflare—no port forwarding or dynamic IP. Traffic goes outbound from host → Cloudflare → your services.

**Website:** https://www.cloudflare.com/products/tunnel/  
**Docs:** https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/  
**GitHub:** https://github.com/cloudflare/cloudflared  
**Docker image:** https://hub.docker.com/r/cloudflare/cloudflared  
**Releases:** https://github.com/cloudflare/cloudflared/releases  

## Quick start (token method)

1. **Cloudflare:** Zero Trust → **Networks → Tunnels → Create tunnel** (Cloudflared). Copy the **tunnel token**.
2. Copy `stack.env.example` → `stack.env` and set `TUNNEL_TOKEN=...`.
3. In the tunnel’s **Public Hostnames**, add routes (e.g. `portainer.yourdomain.com` → HTTP → `localhost:9443`; `status.yourdomain.com` → `localhost:3001`). To route via Caddy, use `localhost:80` (or `443`) and Caddy routes by Host. (Headscale MagicDNS names like `mylaptop.ts.yourdomain.com` resolve on the tailnet only—no tunnel route needed.)
4. Start: `docker compose up -d`.

## Config file (alternative)

1. Copy `config.yml.example` → `config.yml`. Set `tunnel`, hostnames, and services (use `host.docker.internal` for host services).
2. In `docker-compose.yml`, uncomment the `volumes` and `command` that use the config file; remove or leave empty `TUNNEL_TOKEN` if not using token.

## Configuration

| Item | Details |
|------|---------|
| **Env** | `TUNNEL_TOKEN` (from Cloudflare) or config file. See [ENV-VARS.md](../../documents/ENV-VARS.md) and [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) for TZ/locale and shared resources. |

**Benefits:** No open 80/443 on router, no dynamic DNS, origin IP hidden, DDoS protection, optional [Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/applications/).

### Putting logins behind SSO (Cloudflare Access)

To protect specific subdomains (e.g. `portainer.yourdomain.com`) with SSO or one-time PIN instead of basic auth, see **[ACCESS-SSO.md](../../documents/ACCESS-SSO.md)**. Access runs at the Cloudflare edge before traffic reaches the tunnel; no Caddy or tunnel config changes are required.

## Start

`docker compose up -d` from this directory.

## Troubleshooting

### "err name not resolved" but nslookup/dig shows the hostname

If the hostname resolves (e.g. you see AAAA addresses) but the browser or `curl` reports "name not resolved", either Cloudflare is only returning AAAA or your **client’s DNS resolver** is (e.g. only returning AAAA, or stale cache).

**Check:** Run `dig +short <hostname> A` and `dig @1.1.1.1 +short <hostname> A`. If the first is empty but the second returns IPv4 addresses, the issue is your **default resolver**, not Cloudflare.

**Fix (client resolver):** Use a resolver that returns A records: set system or router DNS to **1.1.1.1** (or 8.8.8.8), or flush local DNS cache (e.g. `resolvectl flush-caches` on systemd-resolved, or reboot the device that fails).

**Fix (Cloudflare):** If `dig @1.1.1.1 +short <hostname> A` is also empty, in **Cloudflare Dashboard** → your domain → **DNS** ensure the hostname’s record is **Proxied** (orange cloud). Proxied CNAMEs for tunnels normally get both A and AAAA from Cloudflare.
