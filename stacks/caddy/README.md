# Caddy

Reverse proxy with automatic HTTPS. Proxies to services on the host via `host.docker.internal`. Supports local DNS (e.g. AdGuard Home) and public access (Cloudflare Tunnel or port forwarding).

**Website:** https://caddyserver.com  
**Docs:** https://caddyserver.com/docs/  
**GitHub:** https://github.com/caddyserver/caddy  
**Docker image:** https://hub.docker.com/r/serfriz/caddy-cloudflare  
**Releases:** https://github.com/caddyserver/caddy/releases  

**Sensitive config:** The real `Caddyfile` is gitignored and never committed (domains, email, etc.). Only `Caddyfile.example` lives in the repo.

## Quick start

1. Copy `Caddyfile.example` → `Caddyfile` (gitignored). Edit domain(s) and `email` for Let's Encrypt.
2. For Cloudflare DNS-01 challenge (e.g. with Tunnel or wildcards): copy `stack.env.example` → `stack.env` and set `CLOUDFLARE_API_TOKEN` (see [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens); needs Zone:Read + DNS:Edit).
3. Deploy (see below for Portainer vs host).

## Configuration

| Item | Details |
|------|---------|
| **Ports** | 80, 443 (HTTP/HTTPS) |
| **Volumes** | `./Caddyfile` (ro), `caddy_data` (certs/data) |
| **Env** | Optional: `CLOUDFLARE_API_TOKEN` for DNS-01 (see `stack.env.example`) |
| **Network** | `monitor` — so Uptime Kuma and the metrics stack (Grafana, Prometheus, cAdvisor) can reach Caddy and each other |

- **Local DNS:** Add A records (e.g. `portainer.home`, `kuma.home`) to your resolver so hostnames point at this host. Use `https://portainer.home` etc.
- **Public (your domain):** Use Cloudflare Tunnel (see `stacks/cloudflare-tunnel`) or port forwarding + Let's Encrypt. Set hostnames and email in `Caddyfile`.
- **URL shortener (YOURLS):** The shortener is reverse-proxied at the same hostnames (e.g. short.yourdomain.com, s.yourdomain.com). Login is handled by YOURLS itself (see `stacks/yourls`).
- **Optional HTTP forward proxy:** For CLI tools (e.g. Blackbird) that need to route traffic through Caddy, see the commented block in `Caddyfile.example`. Requires Caddy built with `github.com/caddyserver/forwardproxy`; the default `serfriz/caddy-cloudflare` image does not include it. When enabled, add `3128:3128` to the Caddy stack’s `ports`.

## Building Caddy with plugins

The default `serfriz/caddy-cloudflare` image includes the Cloudflare DNS plugin but not the HTTP forward proxy. To add the forward proxy (for Blackbird and other CLI tools), build a custom Caddy image with [xcaddy](https://github.com/caddyserver/xcaddy). Skip this section if you don’t need the forward proxy.

**1. Install xcaddy** (if needed):

```bash
go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest
```

**2. Build Caddy** — forward proxy only, or both Cloudflare DNS and forward proxy:

```bash
# Forward proxy only (if you don't need Cloudflare DNS)
xcaddy build --with github.com/caddyserver/forwardproxy

# Forward proxy + Cloudflare DNS (to keep both plugins)
xcaddy build \
  --with github.com/caddy-dns/cloudflare \
  --with github.com/caddyserver/forwardproxy
```

**3. Create a Docker image** — from `stacks/caddy`, create a `Dockerfile`:

```dockerfile
FROM golang:1-alpine AS builder
WORKDIR /build
RUN go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest
RUN xcaddy build \
  --with github.com/caddy-dns/cloudflare \
  --with github.com/caddyserver/forwardproxy

FROM caddy:latest
COPY --from=builder /build/caddy /usr/bin/caddy
```

Then build and push:

```bash
cd stacks/caddy
docker build -t harbor.yourdomain.com/homelab/caddy:latest .
docker push harbor.yourdomain.com/homelab/caddy:latest
```

**4. Use the custom image** — update the Caddy stack’s `docker-compose.yml` to use your image instead of `serfriz/caddy-cloudflare`, then uncomment the `:3128 { forward_proxy }` block in your Caddyfile and add `3128:3128` to the Caddy `ports`.

## Deploy (keeping Caddyfile out of the repo)

- **From the host (recommended if you use this repo):** Clone the repo on the server, then in `stacks/caddy` create `Caddyfile` from the example and run `docker compose up -d`. Your real `Caddyfile` stays only on the host.
- **Portainer:** Don’t use “Git repository” for this stack — the repo has no `Caddyfile` (it’s gitignored). Instead:
  1. Put your real `Caddyfile` on the host somewhere only the server can see (e.g. `/opt/caddy/Caddyfile`).
  2. Add stack → **Web editor** (or paste the compose from the repo).
  3. Change the Caddyfile volume to that path, e.g.  
     `./Caddyfile:/etc/caddy/Caddyfile:ro` → `/opt/caddy/Caddyfile:/etc/caddy/Caddyfile:ro`
  4. Deploy. The public repo never sees your domains or email.

## Start

From this directory: `docker compose up -d`.
