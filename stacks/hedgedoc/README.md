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

For advanced SSO (GitHub, GitLab, OIDC), email, and configuration options, refer to the HedgeDoc documentation.

