# Seafile – file sync and sharing

[Seafile](https://www.seafile.com/) is a self-hosted file sync and sharing platform with desktop and mobile clients. This stack runs Seafile with MariaDB and Memcached behind Caddy.

**Website:** https://www.seafile.com/  
**Docs:** https://manual.seafile.com/  
**Docker image:** https://hub.docker.com/r/seafileltd/seafile-mc  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set:
     - `MYSQL_ROOT_PASSWORD` – MariaDB root password,
     - `SEAFILE_DB_PASSWORD` – Seafile DB user password,
     - `SEAFILE_SERVER_HOSTNAME` – your public hostname (e.g. `seafile.yourdomain.com`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Seafile serves HTTP on port `80` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://seafile.yourdomain.com` → `seafile:80`
   - On first visit, follow the Seafile setup wizard to create the admin account.

## Configuration

| Item        | Details                                                                    |
| ----------- | -------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `seafile:80`)                                  |
| **Network** | `monitor` (for Caddy) + default internal network for DB/Memcached          |
| **Images**  | `seafileltd/seafile-mc:latest`, `mariadb:10.11`, `memcached:alpine`        |
| **Storage** | `seafile_db` (MariaDB), `seafile_data` (`/shared` – config/data/logs)      |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `seafile.yourdomain.com` → `seafile:80` |

For advanced configuration (SSL offload details, client settings, email, etc.), refer to the official Seafile Docker documentation.

