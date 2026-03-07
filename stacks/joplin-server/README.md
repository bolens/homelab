# Joplin Server – sync backend

[Joplin Server](https://joplinapp.org/help/server/) is the official synchronization backend for Joplin note-taking clients. This stack runs Joplin Server with Postgres behind Caddy.

**Website:** https://joplinapp.org/  
**Server docs:** https://joplinapp.org/help/server/  
**Docker image:** https://hub.docker.com/r/joplin/server  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set:
     - `POSTGRES_PASSWORD` – DB password,
     - `APP_BASE_URL` – public URL behind Caddy (e.g. `https://joplin.yourdomain.com`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Joplin Server listens on port `22300` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://joplin.yourdomain.com` → `joplin-server:22300`
   - Log into the web UI to create or manage users, then configure Joplin clients with the same URL and credentials.

## Configuration

| Item        | Details                                                                    |
| ----------- | -------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `joplin-server:22300`)                         |
| **Network** | `monitor` (for Caddy) + default internal network for Postgres              |
| **Images**  | `joplin/server:latest`, `postgres:16-alpine`                               |
| **Storage** | `joplin_pg_data` (Postgres)                                                |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `joplin.yourdomain.com` or `joplin-server.yourdomain.com` → `joplin-server:22300` |

## Email / SMTP (optional)

For user invites and notifications, configure SMTP via env vars or the Joplin Server admin UI. For the shared Postfix relay, set in `stack.env`:

- `MAILER_HOST=smtp-relay`
- `MAILER_PORT=587`
- `MAILER_FROM=joplin@yourdomain.com` (must match Postfix `ALLOWED_SENDER_DOMAINS`)
- Leave `MAILER_USERNAME` and `MAILER_PASSWORD` empty for the relay without auth

For **internal-only** (Mailpit): deploy [stacks/postfix](../postfix/README.md) and [stacks/mailpit](../mailpit/README.md) with `RELAYHOST=mailpit:1025`. See [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) and the [Joplin Server docs](https://joplinapp.org/help/server/).

