# Gitea – self-hosted Git service

[Gitea](https://about.gitea.com/) is a lightweight, self-hosted Git service with a web UI, issue tracking, and basic CI integrations.

**Website:** https://about.gitea.com/  
**Docs:** https://docs.gitea.com/  
**Docker image:** https://hub.docker.com/r/gitea/gitea  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set:
     - `GITEA_DB_PASSWORD` – DB password,
     - `GITEA_ROOT_URL` – public URL behind Caddy (e.g. `https://gitea.yourdomain.com`),
     - optionally `USER_UID` / `USER_GID` to match your host user.
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Gitea listens on port `3000` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://gitea.yourdomain.com` → `gitea:3000`
   - Complete the initial web-based setup, pointing the database to `postgres:5432` with the credentials above.

## Deploying via Portainer

1. **Stacks** → **Add stack** → paste the contents of `docker-compose.yml`.
2. **Environment variables** (required):
   - `GITEA_DB_PASSWORD` – Postgres password (e.g. `openssl rand -base64 24`)
   - `GITEA_ROOT_URL` – public URL behind Caddy, e.g. `https://gitea.yourdomain.com`
   - `GITEA_DB_NAME`, `GITEA_DB_USER` (optional; default `gitea`)
   - `USER_UID`, `USER_GID` (optional; default 1000)
3. Ensure the **monitor** network exists.
4. Deploy. On first access, complete the web setup wizard; the database is pre-configured via env vars.

## Create initial admin user (CLI)

If you prefer to create the first admin user via CLI instead of the web wizard:

```bash
docker exec -it gitea gitea admin user create \
  --username git \
  --password YOUR_SECURE_PASSWORD \
  --email your@email.com \
  --admin
```

Generate a password with `openssl rand -base64 24`. Use `--random-password` to have Gitea generate one (check container logs for the value).

## Configuration

| Item        | Details                                                                  |
| ----------- | ------------------------------------------------------------------------ |
| **Access**  | Via Caddy (reverse-proxy to `gitea:3000`)                                |
| **Network** | `monitor` (for Caddy) + default internal network for Postgres            |
| **Images**  | `gitea/gitea:latest`, `postgres:16-alpine`                               |
| **Storage** | `gitea_pg_data` (Postgres), `gitea_data` (`/data` – repos, configs, etc.) |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `gitea.yourdomain.com` → `gitea:3000` |


## Email / SMTP (optional)

For notifications (password reset, issue mentions, etc.), configure mail in **Site administration** → **Configuration** → **Mailer**. Use the shared Postfix relay:

- **SMTP Host:** `smtp-relay` (container name on `monitor` network)
- **SMTP Port:** `587`
- **SMTP User / Password:** leave empty for the relay (no auth)
- **From email:** e.g. `gitea@yourdomain.com`

Ensure your domain is in Postfix `ALLOWED_SENDER_DOMAINS`. For **internal-only** (Mailpit): deploy [stacks/postfix](../postfix/README.md) and [stacks/mailpit](../mailpit/README.md) with `RELAYHOST=mailpit:1025`; view caught emails at `https://mailpit.yourdomain.com`. See [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

Gitea can act as the Git provider for the `woodpecker-ci` stack via OAuth; see that stack’s README for integration notes.

