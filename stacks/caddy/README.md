# Caddy

Reverse proxy with automatic HTTPS. Proxies to services on the host via `host.docker.internal`. Supports local DNS (e.g. AdGuard Home) and public access (Cloudflare Tunnel or port forwarding).

## Quick start

1. Copy `Caddyfile.example` → `Caddyfile` (gitignored). Edit domain(s) and `email` for Let's Encrypt.
2. Deploy: `docker compose up -d` from this directory, or in Portainer add stack via **Git repository** with Compose path to this directory (so `Caddyfile` is present).

## Configuration

| Item | Details |
|------|---------|
| **Ports** | 80, 443 (HTTP/HTTPS) |
| **Volumes** | `./Caddyfile` (ro), `caddy_data` (certs/data) |
| **Network** | `monitor` — so Uptime Kuma can reach `http://caddy:80` |

- **Local DNS:** Add A records (e.g. `portainer.home`, `kuma.home`) to your resolver so hostnames point at this host. Use `https://portainer.home` etc.
- **Public (your domain):** Use Cloudflare Tunnel (see `stacks/cloudflare-tunnel`) or port forwarding + Let's Encrypt. Set hostnames and email in `Caddyfile`.

**Portainer:** Use **Stacks → Add stack → Build method: Git repository** and set the Compose path to this directory. Web-editor-only deploy will fail because the bind-mounted `Caddyfile` won't exist.

## Start

From this directory: `docker compose up -d`.
