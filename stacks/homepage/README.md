# Homepage

Static **landing page** (e.g. “under construction”) for your root domain or a dedicated hostname. One nginx container serves files from `./www`; no database or app logic. Replace the default `www/index.html` with your own content when you are ready.

**Use case:** Serve a simple “under construction” or placeholder page at `https://yourdomain.com` and `https://www.yourdomain.com` (or at `https://homepage.yourdomain.com`) until you deploy a full site.

## Quick start

1. **Environment**  
   Copy `stack.env.example` to `stack.env` (all vars optional).

2. **Content**  
   Edit `www/index.html` if you want to change the default “Under construction” message.

3. **Deploy**  
   From this directory: `docker compose up -d` (or add the stack in Portainer).

4. **Caddy**  
   Add the Caddy site block(s) from [Caddy](#caddy) below to your Caddyfile (copy from `stacks/caddy/Caddyfile.example`). Use your real hostname in the Caddyfile (e.g. `yourdomain.com, www.yourdomain.com` or `homepage.yourdomain.com`). No host ports; access only via Caddy at `homepage:80` on the `monitor` network.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse proxy to `homepage:80`) |
| **Network** | `monitor` (external) |
| **Image** | `nginx:alpine` |
| **Storage** | Bind mount `./www` → `/usr/share/nginx/html` (read-only). Edit files in `www/` on the host. |
| **Env** | Optional `TZ`; see [ENV-VARS.md](../../documents/ENV-VARS.md). TZ/locale can come from shared.env. |

## Caddy

Use one of the following, depending on whether you want this as the **root domain** or a **subdomain**.

**Root domain** (e.g. `https://yourdomain.com` and `https://www.yourdomain.com`):

```
yourdomain.com, www.yourdomain.com {
	tls {
		dns cloudflare {env.CLOUDFLARE_API_TOKEN}
	}
	reverse_proxy homepage:80
}
```

**Subdomain** (e.g. `https://homepage.yourdomain.com`):

```
homepage.yourdomain.com {
	tls {
		dns cloudflare {env.CLOUDFLARE_API_TOKEN}
	}
	reverse_proxy homepage:80
}
```

For **local** access (e.g. `https://homepage.home`), add to the local section of your Caddyfile:

```
homepage.home, homepage.local {
	tls internal
	reverse_proxy homepage:80
}
```

Replace `yourdomain.com` with your actual domain in the Caddyfile (the real Caddyfile is gitignored).

## SSO / Cloudflare Access

This stack serves a public static page. It is typically **not** protected by Cloudflare Access; if you do protect it, configure the hostname in [documents/ACCESS-SSO.md](../../documents/ACCESS-SSO.md) as needed.

## Portainer

1. Ensure the `monitor` network exists (e.g. create it from Networks or deploy Caddy first).
2. Stacks → Add stack → paste this compose (or pull from repo). Set **Web editor** path to this stack’s `docker-compose.yml`.
3. Optionally set environment variables (e.g. `TZ`); defaults work.
4. Add the Caddy site block(s) above to your Caddyfile and reload Caddy.

## Start

`docker compose up -d` from this directory.
