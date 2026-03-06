# Firefly III – personal finance manager

[Firefly III](https://www.firefly-iii.org/) is a self-hosted personal finance manager for tracking accounts, transactions, budgets, and reports.

**Website:** https://www.firefly-iii.org/  
**Docs:** https://docs.firefly-iii.org/  
**Docker image:** https://hub.docker.com/r/fireflyiii/core  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set:
     - `DB_PASSWORD` – DB user password,
     - `APP_URL` – public URL behind Caddy (e.g. `https://firefly.yourdomain.com`),
     - `APP_KEY` – Laravel app key (see below).
2. **Generate APP_KEY**

   ```bash
   docker run --rm fireflyiii/core php artisan key:generate --show
   ```

   Copy the output into `APP_KEY` in `stack.env`.

3. **Deploy**

   ```bash
   docker compose up -d
   ```

4. **Access**
   - Firefly III listens on port `8080` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://firefly.yourdomain.com` → `firefly-iii:8080`

## Configuration

| Item        | Details                                                                      |
| ----------- | ---------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `firefly-iii:8080`)                              |
| **Network** | `monitor` (for Caddy) + default internal network for Postgres                |
| **Images**  | `fireflyiii/core:latest`, `postgres:16-alpine`                               |
| **Storage** | `firefly_pg_data` (DB), `firefly_upload` (uploaded attachments/exports)      |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `firefly-iii.yourdomain.com` → `firefly-iii:8080` |

For advanced configuration (mail, multi-currency, cron jobs, importers), see the official Firefly III documentation.

