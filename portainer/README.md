# Portainer CE

Docker management UI: manage containers, images, volumes, and stacks from a web interface.

## Quick start

1. If you access Portainer through Caddy or another HTTPS reverse proxy (e.g. `https://portainer.yourdomain.com`), copy `stack.env.example` → `stack.env` and set `TRUSTED_ORIGINS` to the **hostname only** (e.g. `portainer.yourdomain.com` — no `https://` or port). Compose converts it to the absolute HTTPS origin required by Portainer. Otherwise you may get **"Forbidden - Invalid origin"** when deploying or logging in.
2. Ensure the shared ingress network exists: `docker network create ingress-admin` (safe to skip if Caddy preparation already created it).
3. `docker compose up -d` from this directory (or deploy as a stack). Open your Caddy URL and complete the initial admin setup.

## Configuration

| Item | Details |
|------|---------|
| **Port** | 9443 internally on `ingress-admin`; no host publication |
| **Volumes** | Docker socket (required), `portainer_data` (persistent) |
| **Network** | `ingress-admin` (dedicated Caddy-to-service ingress) plus the stack-local default network |
| **Security** | `no-new-privileges:true` |
| **Behind proxy** | Set `TRUSTED_ORIGINS` to the hostname only; Compose passes it to Portainer as an absolute HTTPS origin |

Access via Caddy (e.g. `https://portainer.yourdomain.com`) or Cloudflare Tunnel once those stacks are configured.

### "Forbidden - Invalid origin" when deploying stacks

If you use Portainer through an HTTPS reverse proxy (Caddy, Cloudflare Tunnel, etc.), set **TRUSTED_ORIGINS** to the **hostname only** (e.g. `portainer.yourdomain.com` — no `https://` or port). Compose adds the required `https://` scheme.

- **If Portainer is already running:** update `stack.env`, then recreate the container from this Compose file so the hostname is converted to an absolute HTTPS origin. Then reload the Portainer UI.
- **If you deploy Portainer from CLI:** Copy `stack.env.example` → `stack.env`, set `TRUSTED_ORIGINS=portainer.yourdomain.com`, then `docker compose up -d`.

## Start

`docker compose up -d` from this directory.
