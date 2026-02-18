# Exposing your domain via Cloudflare

All Docker stacks (Caddy, Portainer, Uptime Kuma, Cloudflare Tunnel) run on your Docker host.

## Option A: Cloudflare Tunnels (Recommended) ✅

**Use the `cloudflare-tunnel` stack** – no port forwarding needed.

1. Set up the tunnel (see `../cloudflare-tunnel/README.md`)
2. In Cloudflare Zero Trust → Tunnels → Your Tunnel → Public Hostnames:
   - Route `portainer.yourdomain.com` → `localhost:80` (through Caddy)
   - Route `status.yourdomain.com` → `localhost:80` (through Caddy)
3. Caddy handles routing based on Host headers (copy `Caddyfile.example` to `Caddyfile` and set your domain)

**Benefits:** No router config, no dynamic IP management, origin IP hidden.

---

## Option B: Port Forwarding (Legacy)

If you prefer direct port forwarding instead of tunnels:

### 1. DNS in Cloudflare

In **Cloudflare Dashboard → bolens.dev → DNS → Records**, add:

| Type | Name           | Content        | Proxy |
|------|----------------|----------------|-------|
| A    | portainer      | YOUR_PUBLIC_IP | Proxied (orange) or DNS only |
| A    | status         | YOUR_PUBLIC_IP | Proxied or DNS only |

- **Content:** Your home’s public IPv4 (the one your router gets from the ISP). If it changes, use Cloudflare’s dynamic DNS or a script.
- **Proxy:** “Proxied” (orange cloud) = traffic goes through Cloudflare (DDoS hiding, optional WAF). “DNS only” (grey) = direct to your IP.

## 2. Router: port forwarding

Forward on your router to **bamboo.local**:

- **External 80** → bamboo.local IP, port **80**
- **External 443** → bamboo.local IP, port **443**

Caddy is bound to 80/443 on bamboo.local.

## 3. SSL/TLS in Cloudflare

**Cloudflare Dashboard → SSL/TLS:**

- Set encryption mode to **Full (strict)** so Cloudflare expects valid HTTPS on your origin. Caddy will get Let’s Encrypt certs for your domain automatically.

(If you use “Flexible,” Cloudflare→origin is HTTP only; Caddy won’t get certs for the origin. Prefer Full (strict).)

## 4. Optional: lock down sensitive services

**Portainer** is powerful (full Docker control). If you expose it:

- Use a strong admin password and 2FA if available.
- Consider **Cloudflare Zero Trust (Access):** require email or IdP login before reaching your Portainer hostname, so only you (or your team) can open it.

Your status hostname (Uptime Kuma) is often left public so you can check status from anywhere; protect the Uptime Kuma admin account with a strong password.

## 5. Add more services

To expose another app on your domain:

1. Add a **DNS** record (e.g. `app` → A record to your public IP).
2. In **Caddyfile**, add:
   ```
   app.yourdomain.com {
     reverse_proxy host.docker.internal:PORT
   }
   ```
3. Redeploy the Caddy stack and ensure the app’s port is published on the host.

## Summary (Port Forwarding Method)

- **DNS:** Your subdomains (e.g. portainer, status) → your public IP.
- **Router:** Forward 80 and 443 to your Docker host.
- **Cloudflare SSL:** Full (strict).
- **Caddy:** Copy `Caddyfile.example` to `Caddyfile`, set your domain, then deploy for automatic HTTPS.

**Note:** Cloudflare Tunnels (Option A) is recommended and doesn't require port forwarding.
