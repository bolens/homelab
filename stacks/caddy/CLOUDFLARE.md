# Exposing your domain via Cloudflare

All Docker stacks (Caddy, Portainer, Uptime Kuma, Cloudflare Tunnel) run on your Docker host.

## Option A: Cloudflare Tunnels (Recommended) ✅

**Use the `cloudflare-tunnel` stack** – no port forwarding needed.

1. Set up the tunnel (see `../cloudflare-tunnel/README.md`)
2. In Cloudflare Zero Trust → Tunnels → Your Tunnel → Public Hostnames:
   - Route each hostname → **`http://caddy:80`** when `cloudflared` runs in Docker on the **`ingress-admin`** network (same as Caddy). Do **not** use `localhost:80` there, that is the tunnel container’s loopback, not Caddy.
   - Plain-HTTP `reverse_proxy` blocks in stack snippets should use **`transport http { versions 1.1 }`** to the upstream so Caddy 2.11 does not negotiate h2c with apps that only speak HTTP/1.1 (symptom: **HTTP 200, empty body** via the tunnel). Regenerate or run `scripts/patch-caddy-h1-transport.py` after editing snippets.
3. Caddy handles routing based on Host headers (copy `Caddyfile.example` to `Caddyfile` and set your domain). Each app’s **`stacks/<name>/caddy_snippet.conf`** must define **`http://<name>.example.com`** (and usually **`…example.com { tls { dns cloudflare … } }`**) if that hostname should work; snippets that only list **`.home` / `.local`** do not create public routes, see **Split horizon** in [stacks/caddy/README.md](./README.md).

**Benefits:** No router config, no dynamic IP management, origin IP hidden.

### ACME: `No such authorization` (HTTP 404) on new hostnames

After adding many **`*.example.com`** sites at once, Caddy logs may show **`tls.obtain`** errors: **Let's Encrypt `urn:ietf:params:acme:error:malformed`, "No such authorization"** for some identifiers. That is usually **transient** (too many parallel orders, authz reuse timing, or LE-side hiccups). Caddy **retries** (`will retry` / `retrying_in`). If DNS-01 succeeds for the same zone on other names, check **Cloudflare API token** (DNS:Edit), **propagation**, and **[Let’s Encrypt rate limits](https://letsencrypt.org/docs/rate-limits/)**; stagger reloads or wait for retries before assuming a bad snippet.

### Log noise after restarts (Tunnel + Caddy)

You may see **`http.handlers.reverse_proxy`** warnings: **"aborting with incomplete response"** with **`reading: context canceled`**. That usually means the **client closed the connection** before the upstream finished, normal for **SSE** (e.g. Dozzle `/api/events/stream`), **short health-check timeouts** (logs often show **`Blackbox-Exporter`** hitting Cal.com `/auth/login`), or **scanners** hitting `booking.example.com`. It is **not** a broken proxy.

**Optional cleanups (tradeoffs):**

- **Quieter logs:** in the global `{ … }` block of your real `Caddyfile`, add `log { level ERROR }`, hides those warnings but also hides most **`info`** (TLS renewal chatter, etc.).
- **Blackbox:** increase the **HTTP probe timeout** for slow apps, or probe a **lighter URL** than full login pages.
- **Correct HTTPS scheme and hostname to apps:** inside each **`http://*.example.com`** site (tunnel → Caddy on :80 only), add on `reverse_proxy`: `header_up X-Forwarded-Proto https`, and **`header_up Host {host}`** (and usually `header_up X-Forwarded-Host {host}`). Otherwise Caddy may send `Host: upstream:port` to the container; many apps (Servarr, code-server) then return **HTTP 200 with an empty body** or a blank document. Same headers on the matching **`https://*.example.com`** site block help when traffic reaches Caddy on :443 behind Cloudflare.

---

## Option B: Port Forwarding (Legacy)

If you prefer direct port forwarding instead of tunnels:

### 1. DNS in Cloudflare

In **Cloudflare Dashboard → yourdomain.com → DNS → Records**, add:

| Type | Name           | Content        | Proxy |
|------|----------------|----------------|-------|
| A    | portainer      | YOUR_PUBLIC_IP | Proxied (orange) or DNS only |
| A    | status         | YOUR_PUBLIC_IP | Proxied or DNS only |

- **Content:** Your home’s public IPv4 (the one your router gets from the ISP). If it changes, use Cloudflare’s dynamic DNS or a script.
- **Proxy:** "Proxied" (orange cloud) = traffic goes through Cloudflare (DDoS hiding, optional WAF). "DNS only" (grey) = direct to your IP.

## 2. Router: port forwarding

Forward on your router to **bamboo.local**:

- **External 80** → bamboo.local IP, port **80**
- **External 443** → bamboo.local IP, port **443**

Caddy is bound to 80/443 on bamboo.local.

## 3. SSL/TLS in Cloudflare

**Cloudflare Dashboard → SSL/TLS:**

- Set encryption mode to **Full (strict)** so Cloudflare expects valid HTTPS on your origin. Caddy will get Let’s Encrypt certs for your domain automatically.

(If you use "Flexible," Cloudflare→origin is HTTP only; Caddy won’t get certs for the origin. Prefer Full (strict).)

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
