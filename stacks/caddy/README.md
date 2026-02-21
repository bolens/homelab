# Caddy

Reverse proxy with automatic HTTPS. Proxies to services on the host via `host.docker.internal`. Supports local DNS (e.g. AdGuard Home) and public access (Cloudflare Tunnel or port forwarding).

**Sensitive config:** The real `Caddyfile` is gitignored and never committed (domains, email, etc.). Only `Caddyfile.example` lives in the repo.

## Quick start

1. Copy `Caddyfile.example` → `Caddyfile` (gitignored). Edit domain(s) and `email` for Let's Encrypt.
2. For Cloudflare DNS-01 challenge (e.g. with Tunnel or wildcards): copy `.env.example` → `.env` and set `CLOUDFLARE_API_TOKEN` (see [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens); needs Zone:Read + DNS:Edit).
3. Deploy (see below for Portainer vs host).

## Configuration

| Item | Details |
|------|---------|
| **Ports** | 80, 443 (HTTP/HTTPS) |
| **Volumes** | `./Caddyfile` (ro), `caddy_data` (certs/data) |
| **Env** | Optional: `CLOUDFLARE_API_TOKEN` for DNS-01 (see `.env.example`) |
| **Network** | `monitor` — so Uptime Kuma and the metrics stack (Grafana, Prometheus, cAdvisor) can reach Caddy and each other |

- **Local DNS:** Add A records (e.g. `portainer.home`, `kuma.home`) to your resolver so hostnames point at this host. Use `https://portainer.home` etc.
- **Public (your domain):** Use Cloudflare Tunnel (see `stacks/cloudflare-tunnel`) or port forwarding + Let's Encrypt. Set hostnames and email in `Caddyfile`.
- **URL shortener (YOURLS):** The shortener is reverse-proxied at the same hostnames (e.g. short.bolens.dev, s.bolens.dev). Login is handled by YOURLS itself (see `stacks/yourls`).

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
