# BookStack – wiki and documentation

[BookStack](https://www.bookstackapp.com/) is a simple, self-hosted wiki for storing documentation in books, chapters, and pages. This stack runs BookStack with MariaDB behind Caddy. No host ports; access via Caddy.

**Website:** https://www.bookstackapp.com/
**Docs:** https://www.bookstackapp.com/docs/
**GitHub:** https://github.com/BookStackApp/BookStack
**Docker image:** https://docs.linuxserver.io/images/docker-bookstack

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set `APP_URL` to your Caddy hostname (e.g. `https://bookstack.yourdomain.com`).
   - Set `APP_KEY` to `base64:` followed by `openssl rand -base64 32` for a new installation. Existing installations must reuse their persisted key.
   - Set `MYSQL_ROOT_PASSWORD` and `MYSQL_PASSWORD` (e.g. `openssl rand -base64 24`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - BookStack listens on port `80` inside the container.
   - Put it behind Caddy on the `ingress-public` network, e.g.:
     - `https://bookstack.yourdomain.com` → `bookstack:80`
   - Default login: `admin@admin.com` / `password`, **change immediately** in Settings.

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `bookstack:80`)                                 |
| **Network** | `ingress-public` (for Caddy) + default (MariaDB)                             |
| **Images**  | `lscr.io/linuxserver/bookstack:latest`, `lscr.io/linuxserver/mariadb:latest` |
| **Storage** | `bookstack_data`, `bookstack_mariadb`                                       |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `bookstack.yourdomain.com` → `bookstack:80` |

To change `APP_URL` after install:
`docker exec -it bookstack php /app/www/artisan bookstack:update-url OLD_URL NEW_URL`

## Portainer

Add stack from this directory; set `APP_URL`, `MYSQL_ROOT_PASSWORD`, and `MYSQL_PASSWORD` in stack env. No host ports; use Caddy to expose the service.

## Upgrading to BookStack 26.09

BookStack 26.09 requires a nonempty application encryption key. Before upgrading,
verify the existing `APP_KEY` in `/config/www/.env` and preserve it in the backup.
If supplying it through `stack.env`, copy that same key privately; changing it
can make encrypted data unreadable. Preparation preserves existing configuration
and does not generate or replace this key.

Stop BookStack before quiescing MariaDB. Back up both configuration/data volumes
and verify an isolated restore using the previous compatible images. Verify
users, books, chapters, pages, revisions, uploads and the application migration
after updating. Restore both volumes with the previous images on failure.
