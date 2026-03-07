# Linkwarden

Self-hosted bookmark manager and link aggregator: save links, archive pages, organize with collections, full-text search.

**Website:** https://linkwarden.app  
**Docs:** https://docs.linkwarden.app  
**GitHub:** https://github.com/linkwarden/linkwarden  
**Docker image:** https://github.com/linkwarden/linkwarden/pkgs/container/linkwarden  
**Releases:** https://github.com/linkwarden/linkwarden/releases  

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Generate and set `NEXTAUTH_SECRET`, `POSTGRES_PASSWORD`, and `MEILI_MASTER_KEY` (see **Generating keys and secrets** below).
   - If using Caddy or a public URL, set `NEXTAUTH_URL` to `https://your-domain.com/api/v1/auth`.
2. **Deploy:** `docker compose --env-file stack.env up -d` (compose needs env vars for substitution; or add the stack in Portainer and set the same vars in the stack Environment).
3. **First run:** Open Linkwarden (http://host:3000 or via Caddy), register the first user (that user becomes admin).

## Generating keys and secrets

Run these and set the outputs in `stack.env`:

```bash
# NEXTAUTH_SECRET – NextAuth JWT/session signing
openssl rand -base64 32

# POSTGRES_PASSWORD – Postgres DB password
openssl rand -base64 24

# MEILI_MASTER_KEY – Meilisearch API key (hex)
openssl rand -hex 24
```

Set each variable to the corresponding output. See `stack.env.example` for variable names.

**Portainer:** No `.env` file is used; set `NEXTAUTH_SECRET`, `POSTGRES_PASSWORD`, `MEILI_MASTER_KEY` (and optionally `NEXTAUTH_URL`, `TZ`) in the stack’s Environment variables when deploying.
The stack uses **named volumes** (`lw_pgdata`, `lw_data`, `lw_meili_data`) so it works when deployed from Portainer’s web editor.

## Configuration

| Item | Details |
|------|---------|
| **Port** | 3000 (proxied via Caddy; host port exposed for direct access if needed) |
| **Network** | `monitor` (external) — Caddy can reverse-proxy to `linkwarden:3000` |
| **Images** | linkwarden, postgres:16-alpine, getmeili/meilisearch |
| **Env** | `NEXTAUTH_SECRET`, `POSTGRES_PASSWORD`, `MEILI_MASTER_KEY` required; `NEXTAUTH_URL`, `TZ` optional |
| **Storage** | Named volumes: `lw_data` (screenshots, PDFs, profile photos), `lw_pgdata`, `lw_meili_data` |

## Notes

- After changing `stack.env`, run `docker compose --env-file stack.env down && docker compose --env-file stack.env up -d` (restart is not enough for env changes).
- **`NO_SECRET` / MissingSecretError:** NextAuth requires a non-empty `NEXTAUTH_SECRET`. Set it in `stack.env` (e.g. `openssl rand -base64 32`), then recreate the stack with `docker compose --env-file stack.env down && docker compose --env-file stack.env up -d`. If using Portainer, add `NEXTAUTH_SECRET` to the stack’s Environment.
- Optional: SMTP for email verification, S3/Spaces for storage, and many SSO providers — see [environment variables](https://docs.linkwarden.app/self-hosting/environment-variables) and the full [.env.sample](https://github.com/linkwarden/linkwarden/blob/main/.env.sample).

## Email / SMTP (optional)

For email verification and password recovery, use the shared **Postfix** relay. See [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) and [stacks/postfix/README.md](../postfix/README.md).

Add to `stack.env`:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_EMAIL_PROVIDER` | `true` |
| `EMAIL_FROM` | `noreply@yourdomain.com` |
| `EMAIL_SERVER` | `smtp://smtp-relay:587` (no auth; for STARTTLS on 587) |

Ensure your domain is in Postfix `ALLOWED_SENDER_DOMAINS`. **Internal-only (Mailpit):** If Postfix uses `RELAYHOST=mailpit:1025`, view caught emails at `https://mailpit.yourdomain.com`.
