# Naisho

Send personal data deletion request emails to hundreds of data brokers at once. Free, open-source Rails app: you compose your request, pick which companies to contact, and Naisho sends the emails via SMTP.

**Website:** https://naisho.app  
**Docs:** https://github.com/nshki/naisho#readme  
**GitHub:** https://github.com/nshki/naisho  
**Releases:** https://github.com/nshki/naisho/releases  

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `SECRET_KEY_BASE`: `openssl rand -hex 64`

2. **Deploy:** `docker compose --env-file stack.env up -d` (first run builds from GitHub and may take a few minutes).  
   Or add the stack in Portainer and set `SECRET_KEY_BASE` in the stack Environment.

3. **Access:** Open via Caddy (e.g. https://naisho.home or https://naisho.yourdomain.com).  
   On first request the entrypoint runs `db:prepare` and `Company.sync_all` (data broker list).

4. **SMTP:** Configure SMTP in the Naisho UI when sending deletion requests (per-request or default). You can use the `postfix` (smtp-relay) stack: in Naisho use host `smtp-relay` and port `587` if both stacks are on the `monitor` network. For shared SMTP relay setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse proxy to `naisho:3000`) |
| **Network** | `monitor` (Caddy → naisho) |
| **Image** | Built from https://github.com/nshki/naisho (Dockerfile in repo) |
| **Env** | `SECRET_KEY_BASE` (required); optional `TZ`, `RAILS_LOG_LEVEL` |
| **Storage** | Named volume `naisho-data` (SQLite at `/data`) |

## Caddy reverse proxy

Example Caddy vhost:

```
naisho.home, naisho.local {
  tls internal
  reverse_proxy naisho:3000
}
```

Ensure the stack is on the `monitor` network so Caddy can reach `naisho:3000`.

## Start

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose, set `SECRET_KEY_BASE` in **Environment**, deploy.
