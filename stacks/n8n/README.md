# n8n

Workflow automation: connect apps, APIs, and services with a visual editor. Self-hosted alternative to Zapier/Make. Uses SQLite by default (data in Docker volume); optional Postgres for scaling.

**Website:** https://n8n.io  
**Docs:** https://docs.n8n.io/  
**GitHub:** https://github.com/n8n-io/n8n  
**Docker image:** https://hub.docker.com/r/n8nio/n8n  
**Releases:** https://github.com/n8n-io/n8n/releases  

## Quick start

1. Ensure `proxy-ingress` and `mail-services` exist (or run `./prepare-stack.sh`).
2. Copy `stack.env.example` to `stack.env` and set **N8N_HOST** and **WEBHOOK_URL** to the URL where you’ll reach n8n behind Caddy (e.g. `https://n8n.home` or `https://n8n.yourdomain.com`). Both must match your Caddy hostname.
3. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer).
4. Open the URL above; create the owner account on first visit.

## Portainer

The stack is Portainer-friendly with env defaults for TZ/locale, `proxy-ingress` for Caddy, and `mail-services` for SMTP. Set **N8N_HOST** and **WEBHOOK_URL** in the stack Environment (e.g. `https://n8n.yourdomain.com`).

## Configuration

| Item | Details |
|------|---------|
| **Ports** | None; access only via Caddy (`reverse_proxy n8n:5678` on `proxy-ingress`). |
| **Volumes** | `n8n_data` → `/home/node/.n8n` (SQLite DB, encryption key, workflows). Back this up. |
| **Network** | `proxy-ingress` for Caddy; `mail-services` for SMTP. |
| **Env** | **N8N_HOST** and **WEBHOOK_URL** required when behind Caddy. Optional: `N8N_ENCRYPTION_KEY` (e.g. `openssl rand -hex 32`) so credentials survive volume recreation. For TZ/locale and shared resources (e.g. SMTP relay), see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) and [ENV-VARS.md](../../documents/ENV-VARS.md). |

## Email (SMTP)

To send emails from workflows (e.g. **Send Email** node), configure SMTP in n8n: **Settings** → **Community nodes** / **Credentials** → add an SMTP credential. Use the shared Postfix relay:

- **Host:** `smtp-relay`
- **Port:** `587`
- **Secure:** off (STARTTLS is negotiated)
- **User / Password:** leave empty when using the internal relay (no auth)

For **internal-only** (Mailpit): deploy [stacks/postfix](../postfix/README.md) and [stacks/mailpit](../mailpit/README.md) with `RELAYHOST=mailpit:1025`. All emails appear in the Mailpit web UI at `https://mailpit.yourdomain.com`; none are delivered externally. See [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

## Caddy

Use `reverse_proxy n8n:5678`. Add blocks for `n8n.home` / `n8n.local` (local TLS) and your public host (e.g. `n8n.yourdomain.com`). See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example).

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
