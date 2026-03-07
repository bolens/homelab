# HedgeDoc – collaborative markdown editor

[HedgeDoc](https://hedgedoc.org/) is a collaborative markdown editor for real-time note taking and documentation, similar to HackMD. This stack runs HedgeDoc with Postgres behind Caddy.

**Website:** https://hedgedoc.org/  
**Docs:** https://docs.hedgedoc.org/  
**Docker image:** https://quay.io/repository/hedgedoc/hedgedoc  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set:
     - `POSTGRES_PASSWORD` – DB password,
     - `CMD_DOMAIN` – public hostname (e.g. `hedgedoc.yourdomain.com`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - HedgeDoc listens on port `3000` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://hedgedoc.yourdomain.com` → `hedgedoc:3000`

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `hedgedoc:3000`)                                |
| **Network** | `monitor` (for Caddy) + default internal network for Postgres               |
| **Images**  | `quay.io/hedgedoc/hedgedoc:1.9.9`, `postgres:16-alpine`                     |
| **Storage** | `hedgedoc_pg_data` (DB), `hedgedoc_uploads` (uploaded attachments)          |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `hedgedoc.yourdomain.com` → `hedgedoc:3000` |

## Email / SMTP (optional)

For password reset and invites, configure SMTP via env vars (see [HedgeDoc config](https://docs.hedgedoc.org/setup/config-variables/)). For the shared Postfix relay, add to `stack.env`:

- `CMD_EMAIL=true`
- `CMD_SMTP_HOST=smtp-relay`
- `CMD_SMTP_PORT=587`
- `CMD_SMTP_FROM=hedgedoc@yourdomain.com` (must match Postfix `ALLOWED_SENDER_DOMAINS`)
- Leave `CMD_SMTP_USER` and `CMD_SMTP_PASS` empty for the relay without auth

For **internal-only** (Mailpit): deploy [stacks/postfix](../postfix/README.md) and [stacks/mailpit](../mailpit/README.md) with `RELAYHOST=mailpit:1025`. See [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

For advanced SSO (GitHub, GitLab, OIDC) and other options, refer to the HedgeDoc documentation.

