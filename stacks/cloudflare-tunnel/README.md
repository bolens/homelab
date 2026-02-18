# Cloudflare Tunnel (cloudflared)

Runs on your Docker host (same machine as Portainer, Caddy, Uptime Kuma). Exposes those services via Cloudflare Tunnels—no port forwarding or dynamic IP management. Traffic flows outbound from bamboo.local to Cloudflare, then Cloudflare routes it to your services.

## Setup

### 1. Create Tunnel in Cloudflare

1. Go to **Cloudflare Dashboard → Zero Trust** (or https://one.dash.cloudflare.com/)
2. **Networks → Tunnels → Create a tunnel**
3. Choose **Cloudflared** as connector
4. Name it (e.g., "homelab")
5. Copy the **Tunnel token** (starts with something like `eyJ...`)

### 2. Configure Routes in Cloudflare Dashboard

In the tunnel’s **Public Hostnames** tab, add routes:

| Subdomain | Service | Type | URL |
|-----------|---------|------|-----|
| `portainer.yourdomain.com` | Portainer | HTTP | `localhost:9443` |
| `status.yourdomain.com` | Uptime Kuma | HTTP | `localhost:3001` |

**Note:** If routing through Caddy instead of directly:
- Set URL to `localhost:80` (or `localhost:443` if Caddy handles HTTPS)
- Caddy will then route based on Host header

### 3. Set Token and Start

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and paste your tunnel token:
   ```
   TUNNEL_TOKEN=eyJ...
   ```

3. Start the stack:
   ```bash
   docker compose up -d
   ```

The tunnel will connect outbound to Cloudflare. No router port forwarding needed.

## Alternative: Config File Method

If you prefer a config file instead of a token:

1. Copy `config.yml.example` to `config.yml` and set your tunnel ID and hostnames:
   ```yaml
   tunnel: YOUR_TUNNEL_ID
   credentials-file: /etc/cloudflared/credentials.json
   
   ingress:
     - hostname: portainer.yourdomain.com
       service: http://host.docker.internal:9443
     - hostname: status.yourdomain.com
       service: http://host.docker.internal:3001
     - service: http_status:404
   ```

2. Update `docker-compose.yml` to use the config file (see commented section).

## Benefits vs Port Forwarding

- ✅ No router port forwarding (80/443 don’t need to be open)
- ✅ No dynamic IP management (tunnel connects outbound)
- ✅ Origin IP hidden (Cloudflare proxies traffic)
- ✅ Built-in DDoS protection
- ✅ Optional: Cloudflare Access for authentication
