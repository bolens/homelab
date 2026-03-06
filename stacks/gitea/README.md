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

## Configuration

| Item        | Details                                                                  |
| ----------- | ------------------------------------------------------------------------ |
| **Access**  | Via Caddy (reverse-proxy to `gitea:3000`)                                |
| **Network** | `monitor` (for Caddy) + default internal network for Postgres            |
| **Images**  | `gitea/gitea:latest`, `postgres:16-alpine`                               |
| **Storage** | `gitea_pg_data` (Postgres), `gitea_data` (`/data` – repos, configs, etc.) |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `gitea.yourdomain.com` → `gitea:3000` |

Gitea can act as the Git provider for the `woodpecker-ci` stack via OAuth; see that stack’s README for integration notes.

