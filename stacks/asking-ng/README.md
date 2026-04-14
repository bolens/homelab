# asking-ng

Lightweight poll application (frontend + API + PostgreSQL) for homelab deployment.

- Homepage: https://asking.one
- GitHub: https://github.com/jdleo/asking

## Hostname

- Placeholder public URL: `https://asking-ng.example.com`
- Internal Caddy target: `http://asking-ng-frontend:3000`

## Quick start

1. Prepare local config files:
   - `./prepare-stack.sh`
2. Edit `stack.env` and set strong credentials (`POSTGRES_PASSWORD`).
3. (Optional) Edit `caddy_snippet.conf` and replace placeholder hostname.
4. Start stack:
   - `docker compose up -d --build`

## Local development (pnpm)

The **client** and **api** each have their own `package.json` and `pnpm-lock.yaml`. Use [pnpm](https://pnpm.io/) with [Corepack](https://nodejs.org/api/corepack.html) (`corepack enable`) so the `packageManager` version in each `package.json` is honored.

```bash
# API (port 3001 by default)
cd stacks/asking-ng/api && pnpm install && pnpm start

# Client (from another terminal; Vite on 3000)
cd stacks/asking-ng/client && pnpm install && pnpm start
```

Or from `stacks/asking-ng/client`: `./start-all.sh` starts the API in the background, then the client.

## Notes

- **asking-ng** extends the upstream [jdleo/asking](https://github.com/jdleo/asking) idea: same strawpoll-style API (`/poll`, string poll IDs, `votes` table), plus admin UI, audit logs, and a single Postgres-backed Sequelize schema (no duplicate `polls` tables).
- Caddy should route **`/api/*`** to `asking-ng-api:3001` with `handle_path` so the API still sees `/poll`, `/admin`, etc. The browser uses `VITE_API_BASE=/api` so the client requests `/api/poll`, `/api/admin`, …
- `docker-compose.dev.yml` / `docker-compose.prod.yml` in this folder are reference layouts; homelab deploy uses `docker-compose.yml`.
- All services join the external `monitor` network; Postgres data persists in volume `asking_ng_pg_data`.
- Set **`ADMIN_TOKEN`** in `stack.env` for `/admin/*` routes. `GET /admin/me` only checks that token.

