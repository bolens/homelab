# Linkwarden

Self-hosted bookmark manager and link aggregator: save links, archive pages, organize with collections, full-text search.

**Website:** https://linkwarden.app  
**Docs:** https://docs.linkwarden.app  
**GitHub:** https://github.com/linkwarden/linkwarden

## Quick start

1. **Environment**
   - Copy `.env.example` to `.env`.
   - Set `NEXTAUTH_SECRET` (e.g. `openssl rand -base64 32`).
   - Set `POSTGRES_PASSWORD` to a strong value.
   - Set `MEILI_MASTER_KEY` for Meilisearch (e.g. `openssl rand -hex 24`).
   - If using Caddy or a public URL, set `NEXTAUTH_URL` to `https://your-domain.com/api/v1/auth`.
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer and set the same vars in the stack Environment).
3. **First run:** Open Linkwarden (http://host:3000 or via Caddy), register the first user (that user becomes admin).

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

- After changing `.env`, run `docker compose down && docker compose up -d` (restart is not enough for env changes).
- **`NO_SECRET` / MissingSecretError:** NextAuth requires a non-empty `NEXTAUTH_SECRET`. Set it in `.env` (e.g. `openssl rand -base64 32`), then recreate the stack with `docker compose down && docker compose up -d`. If using Portainer, add `NEXTAUTH_SECRET` to the stack’s Environment.
- Optional: SMTP for email verification, S3/Spaces for storage, and many SSO providers — see [environment variables](https://docs.linkwarden.app/self-hosting/environment-variables) and the full [.env.sample](https://github.com/linkwarden/linkwarden/blob/main/.env.sample).
