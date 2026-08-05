# authentik – identity provider / SSO

[authentik](https://goauthentik.io/) is an open-source identity provider and access management platform. It can act as an OIDC/OAuth2/SAML IdP for your other stacks (e.g. Outline, Grafana, Immich, Linkwarden) and integrates well with reverse proxies and Kubernetes/containers.

**Website:** https://goauthentik.io/  
**Docs:** https://goauthentik.io/docs/  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set at least:
     - `AUTHENTIK_SECRET_KEY` – core secret key (e.g. `openssl rand -base64 50`),
     - `PG_PASS` – Postgres password,
     - `AUTHENTIK_HOST` – public URL behind Caddy (e.g. `https://authentik.yourdomain.com`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - The server listens on port `9000` inside the container by default.
   - Put it behind Caddy on the `ingress-sensitive` network, e.g.:
     - `https://authentik.yourdomain.com` → `authentik-server:9000`
   - On first login, use the setup flow to create the initial admin user.

## Configuration

| Item        | Details                                                                         |
| ----------- | ------------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `authentik-server:9000`)                            |
| **Network** | `ingress-sensitive` for Caddy + `mail-clients` for SMTP + `authentik` internal for DB/Redis |
| **Images**  | `ghcr.io/goauthentik/server:latest`, `postgres:16-alpine`, `redis:alpine`       |
| **Storage** | `authentik_pg_data` (Postgres), `authentik_media` (media/uploads), `authentik_templates` |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `authentik.yourdomain.com` → `authentik-server:9000` |

The `server` and `worker` containers share configuration via environment variables and volumes:

- Database: `AUTHENTIK_POSTGRESQL__*` vars (host `postgres`, db/user/password from `PG_*`).
- Redis: `AUTHENTIK_REDIS__HOST=redis`, `AUTHENTIK_REDIS__PORT=6379`.
- Host: `AUTHENTIK_HOST` should match your Caddy URL.

## Integrations

- Use authentik as an OIDC/OAuth2 IdP for:
  - Web apps that support OAuth/OIDC (Outline, Grafana, Immich, Linkwarden, LibreChat, etc.).
  - Cloudflare Access, if you want authentik to act as the backing IdP.
- Typical pattern:
  - Configure an **application** in authentik for each service.
  - Use the app’s Caddy URL as the redirect URI.
  - Configure the app with authentik’s discovery URL and client credentials.

## Troubleshooting

**authentik-worker unhealthy:** If `authentik-redis` restarts while `authentik-worker` is up, the worker's Celery consumer can hit `NOAUTH` errors or DNS failures, stall its heartbeat, and never recover on its own. Fix: `docker restart authentik-worker`. The server continues handling requests while the worker is down; background tasks (outpost sync, policy refresh, scheduled cleanup) resume immediately after restart. See [TROUBLESHOOTING.md](../../documents/TROUBLESHOOTING.md#authentik-worker-unhealthy-after-redis-restart).

## Email / SMTP (optional)

For password reset and verification emails, configure SMTP in authentik: **System** → **Email** (or **Directory** → **Settings**). Use the shared **Postfix** relay:

- **Host:** `smtp-relay`
- **Port:** `587`
- **Username / Password:** leave empty for the relay (no auth)
- **From:** `authentik@yourdomain.com` (must match Postfix `ALLOWED_SENDER_DOMAINS`)

Ensure Authentik and Postfix are on `mail-clients`. For **internal-only** (Mailpit): deploy [stacks/postfix](../postfix/README.md) and [stacks/mailpit](../mailpit/README.md) with `RELAYHOST=mailpit:1025`; all emails appear in the Mailpit web UI. See [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

## Notes

- This stack mirrors the official docker-compose layout in a simplified form. For advanced configuration (outposts, providers, etc.), refer to the authentik docs.
- Consider pinning a specific image tag instead of `latest` for production deployments.
