# Portainer CE

Docker management UI: manage containers, images, volumes, and stacks from a web interface.

## Quick start

`docker compose up -d` from this directory (or deploy as a stack). Open https://localhost:9443 and complete the initial admin setup.

## Configuration

| Item | Details |
|------|---------|
| **Port** | 9443 (HTTPS only) |
| **Volumes** | Docker socket (required), `portainer_data` (persistent) |
| **Security** | `no-new-privileges:true` |

Access via Caddy (e.g. `https://portainer.home`) or Cloudflare Tunnel once those stacks are configured.

## Start

`docker compose up -d` from this directory.
