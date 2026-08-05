# Woodpecker CI – lightweight CI/CD

[Woodpecker CI](https://woodpecker-ci.org/) is a lightweight, Docker-native CI/CD system. This stack runs a Woodpecker server and agent with Postgres, designed to integrate with your `gitea` stack as the Git provider.

**Website:** https://woodpecker-ci.org/  
**Docs:** https://woodpecker-ci.org/docs/  
**Docker images:** `woodpeckerci/woodpecker-server`, `woodpeckerci/woodpecker-agent`  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set `POSTGRES_PASSWORD` and the same password inside `WOODPECKER_DATABASE_DATASOURCE` (see the `REPLACE_DB_PASSWORD` placeholder in the example).
   - Set `WOODPECKER_GITEA_URL`, `WOODPECKER_GITEA_CLIENT`, `WOODPECKER_GITEA_SECRET`, and `WOODPECKER_AGENT_SECRET`.
   - Optional: `WOODPECKER_HOST` (public Woodpecker URL for OAuth redirects).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Migrating from the old layout** (`WOODPECKER_DB_PASSWORD` only)

   If your `stack.env` still has `WOODPECKER_DB_NAME` / `WOODPECKER_DB_USER` / `WOODPECKER_DB_PASSWORD` but not the Postgres-native variables, add:

   - `POSTGRES_DB` and `POSTGRES_USER` (usually `woodpecker` / `woodpecker`),
   - `POSTGRES_PASSWORD` — same value as the old `WOODPECKER_DB_PASSWORD`,
   - `WOODPECKER_DATABASE_DRIVER=postgres`,
   - `WOODPECKER_DATABASE_DATASOURCE=postgres://woodpecker:YOUR_PASSWORD@woodpecker-postgres:5432/woodpecker?sslmode=disable`.

   Then remove the obsolete `WOODPECKER_DB_*` lines if you like, and recreate the stack (`docker compose up -d --force-recreate`).

4. **If you see `pq: password authentication failed` (28P01)**

   Postgres only applies `POSTGRES_PASSWORD` on **first** volume init. If the role password no longer matches `stack.env`, fix it with:

   ```bash
   docker exec -i woodpecker-postgres psql -U woodpecker -d woodpecker -c "ALTER USER woodpecker WITH PASSWORD 'same-as-POSTGRES_PASSWORD-in-stack-env';"
   docker compose up -d --force-recreate server
   ```

   Also ensure the password inside `WOODPECKER_DATABASE_DATASOURCE` matches. Alternatively, wipe the `woodpecker_pg_data` volume and redeploy (destroys Woodpecker DB data).

5. **Access**
   - Woodpecker server listens on port `8000` (HTTP API/UI) and `9000` (gRPC) inside the container by default.
   - Put it behind Caddy on the `proxy-ingress` network, e.g.:
     - `https://ci.yourdomain.com` → `woodpecker-server:8000`

## Configuration

| Item        | Details                                                                              |
| ----------- | ------------------------------------------------------------------------------------ |
| **Access**  | Via Caddy (reverse-proxy to `woodpecker-server:8000`)                                |
| **Network** | `proxy-ingress` for Caddy + default internal network for Postgres and agent          |
| **Images**  | `woodpeckerci/woodpecker-server:v3`, `woodpeckerci/woodpecker-agent:v3`, `postgres:16-alpine` (`:latest` was removed upstream; pin `v3.x.y` if you want a fixed patch) |
| **Storage** | `woodpecker_pg_data` (DB)                                                            |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `woodpecker-ci.yourdomain.com` or `ci.yourdomain.com` → `woodpecker-server:8000` |

## Gitea integration

- In Gitea:
  - Create an OAuth2 application with redirect URL pointing at the Woodpecker server URL (see Woodpecker docs for exact path).
  - Copy the client ID/secret into `WOODPECKER_GITEA_CLIENT` / `WOODPECKER_GITEA_SECRET`.
- In Woodpecker:
  - Access the UI at `https://ci.yourdomain.com`, sign in via Gitea, and enable repositories for builds.

The `woodpecker-agent` runs builds on the same Docker host, using the Docker socket (`/var/run/docker.sock`) to launch build containers.
