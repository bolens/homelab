# Cloudflare Tunnel (cloudflared)

Exposes services on your Docker host via Cloudflare—no port forwarding or dynamic IP. Traffic goes outbound from host → Cloudflare → your services.

## Quick start (token method)

1. **Cloudflare:** Zero Trust → **Networks → Tunnels → Create tunnel** (Cloudflared). Copy the **tunnel token**.
2. Copy `.env.example` → `.env` and set `TUNNEL_TOKEN=...`.
3. In the tunnel’s **Public Hostnames**, add routes (e.g. `portainer.yourdomain.com` → HTTP → `localhost:9443`; `status.yourdomain.com` → `localhost:3001`). To route via Caddy, use `localhost:80` (or `443`) and Caddy routes by Host.
4. Start: `docker compose up -d`.

## Config file (alternative)

1. Copy `config.yml.example` → `config.yml`. Set `tunnel`, hostnames, and services (use `host.docker.internal` for host services).
2. In `docker-compose.yml`, uncomment the `volumes` and `command` that use the config file; remove or leave empty `TUNNEL_TOKEN` if not using token.

## Configuration

| Item | Details |
|------|---------|
| **Env** | `TUNNEL_TOKEN` (from Cloudflare) or config file. See [ENV-VARS.md](../ENV-VARS.md) for TZ/locale. |

**Benefits:** No open 80/443 on router, no dynamic DNS, origin IP hidden, DDoS protection, optional Cloudflare Access.

## Start

`docker compose up -d` from this directory.
