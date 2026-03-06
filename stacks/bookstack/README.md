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
   - Set `MYSQL_ROOT_PASSWORD` and `MYSQL_PASSWORD` (e.g. `openssl rand -base64 24`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - BookStack listens on port `80` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://bookstack.yourdomain.com` → `bookstack:80`
   - Default login: `admin@admin.com` / `password` — **change immediately** in Settings.

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `bookstack:80`)                                 |
| **Network** | `monitor` (for Caddy) + default (MariaDB)                                   |
| **Images**  | `lscr.io/linuxserver/bookstack:latest`, `lscr.io/linuxserver/mariadb:latest` |
| **Storage** | `bookstack_data`, `bookstack_mariadb`                                       |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `bookstack.yourdomain.com` → `bookstack:80` |

To change `APP_URL` after install:  
`docker exec -it bookstack php /app/www/artisan bookstack:update-url OLD_URL NEW_URL`

## Portainer

Add stack from this directory; set `APP_URL`, `MYSQL_ROOT_PASSWORD`, and `MYSQL_PASSWORD` in stack env. No host ports; use Caddy to expose the service.
