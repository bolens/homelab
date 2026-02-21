# n8n

Workflow automation: connect apps, APIs, and services with a visual editor. Self-hosted alternative to Zapier/Make. Uses SQLite by default (data in Docker volume); optional Postgres for scaling.

## Quick start

1. Ensure the `monitor` network exists (e.g. `docker network create monitor` or deploy Caddy first).
2. Copy `.env.example` to `.env` and set **N8N_HOST** and **WEBHOOK_URL** to the URL where you’ll reach n8n behind Caddy (e.g. `https://n8n.home` or `https://n8n.bolens.dev`). Both must match your Caddy hostname.
3. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer).
4. Open the URL above; create the owner account on first visit.

## Portainer

The stack is Portainer-friendly: env defaults for TZ/locale, optional host port, and external `monitor` network. Set **N8N_HOST** and **WEBHOOK_URL** in the stack Environment (e.g. `https://n8n.bolens.dev`).

## Configuration

| Item | Details |
|------|---------|
| **Ports** | None; access only via Caddy (`reverse_proxy n8n:5678` on the monitor network). |
| **Volumes** | `n8n_data` → `/home/node/.n8n` (SQLite DB, encryption key, workflows). Back this up. |
| **Network** | `monitor` (external) — same as Caddy, Grafana, Dozzle. |
| **Env** | **N8N_HOST** and **WEBHOOK_URL** required when behind Caddy. Optional: `N8N_ENCRYPTION_KEY` (e.g. `openssl rand -hex 32`) so credentials survive volume recreation. See [ENV-VARS.md](../../documents/ENV-VARS.md) for TZ/locale. |

## Caddy

Use `reverse_proxy n8n:5678`. Add blocks for `n8n.home` / `n8n.local` (local TLS) and your public host (e.g. `n8n.bolens.dev`). See [stacks/caddy/Caddyfile](../caddy/Caddyfile) and Caddyfile.example.

## Optional: local files for workflows

To use the **Read/Write Files from Disk** node with a host directory, add a bind mount in `docker-compose.yml`:

```yaml
volumes:
  - n8n_data:/home/node/.n8n
  - ./local-files:/files
```

Create `local-files` on the host; in n8n use path `/files`.

## Start

`docker compose up -d` from this directory.
