# Nextcloud – personal cloud storage

[Nextcloud](https://nextcloud.com/) is a self-hosted file sync and sharing platform with support for calendar, contacts, tasks, and many apps. This stack runs Nextcloud behind Caddy with Postgres and Redis.

**Website:** https://nextcloud.com/  
**Docs:** https://docs.nextcloud.com/server/latest/admin_manual/  
**Docker image:** https://hub.docker.com/_/nextcloud  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set:
     - `POSTGRES_PASSWORD` – strong DB password,
     - `NEXTCLOUD_ADMIN_PASSWORD` – initial admin password,
     - `NEXTCLOUD_TRUSTED_DOMAINS` – your public hostname (e.g. `nextcloud.yourdomain.com`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Nextcloud listens on port `80` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://nextcloud.yourdomain.com` → `nextcloud:80`
   - Open the URL and log in with `NEXTCLOUD_ADMIN_USER` / `NEXTCLOUD_ADMIN_PASSWORD`.

## Configuration

| Item        | Details                                                                      |
| ----------- | ---------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `nextcloud:80`)                                  |
| **Network** | `monitor` (for Caddy and monitoring) + default internal network for DB/Redis |
| **Images**  | `nextcloud:apache`, `postgres:16-alpine`, `redis:alpine`                     |
| **Storage** | `nextcloud_html` (app files/config), `nextcloud_data` (user data), `nextcloud_pg_data` (DB) |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `nextcloud.yourdomain.com` → `nextcloud:80` |

## Notes

- Configure additional apps, external storage, and clients using the Nextcloud admin UI.
- For large deployments, consider separate Redis configuration, object storage for primary/secondary storage, and tuning PHP settings as described in the Nextcloud admin manual.

