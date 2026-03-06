# Woodpecker CI – lightweight CI/CD

[Woodpecker CI](https://woodpecker-ci.org/) is a lightweight, Docker-native CI/CD system. This stack runs a Woodpecker server and agent with Postgres, designed to integrate with your `gitea` stack as the Git provider.

**Website:** https://woodpecker-ci.org/  
**Docs:** https://woodpecker-ci.org/docs/  
**Docker images:** `woodpeckerci/woodpecker-server`, `woodpeckerci/woodpecker-agent`  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set:
     - `WOODPECKER_DB_PASSWORD` – DB password,
     - `WOODPECKER_GITEA_URL` – e.g. `https://gitea.yourdomain.com`,
     - `WOODPECKER_GITEA_CLIENT` / `WOODPECKER_GITEA_SECRET` – from a Gitea OAuth2 app,
     - `WOODPECKER_AGENT_SECRET` – shared secret between server and agent.
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Woodpecker server listens on port `8000` (HTTP API/UI) and `9000` (gRPC) inside the container by default.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://ci.yourdomain.com` → `woodpecker-server:8000`

## Configuration

| Item        | Details                                                                              |
| ----------- | ------------------------------------------------------------------------------------ |
| **Access**  | Via Caddy (reverse-proxy to `woodpecker-server:8000`)                                |
| **Network** | `monitor` (for Caddy) + default internal network for Postgres and agent              |
| **Images**  | `woodpeckerci/woodpecker-server:latest`, `woodpeckerci/woodpecker-agent:latest`, `postgres:16-alpine` |
| **Storage** | `woodpecker_pg_data` (DB)                                                            |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `woodpecker-ci.yourdomain.com` or `ci.yourdomain.com` → `woodpecker-server:8000` |

## Gitea integration

- In Gitea:
  - Create an OAuth2 application with redirect URL pointing at the Woodpecker server URL (see Woodpecker docs for exact path).
  - Copy the client ID/secret into `WOODPECKER_GITEA_CLIENT` / `WOODPECKER_GITEA_SECRET`.
- In Woodpecker:
  - Access the UI at `https://ci.yourdomain.com`, sign in via Gitea, and enable repositories for builds.

The `woodpecker-agent` runs builds on the same Docker host, using the Docker socket (`/var/run/docker.sock`) to launch build containers.

