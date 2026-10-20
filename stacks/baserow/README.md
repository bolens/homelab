# Baserow – self-hosted Airtable alternative

[Baserow](https://baserow.io/) is an open-source no-code database and spreadsheet (tables, views, API). This all-in-one image runs embedded PostgreSQL and Redis; for production or heavy use you can separate those services (see [Baserow Docker docs](https://baserow.io/docs/installation/install-with-docker-compose)). No host ports; put it behind Caddy.

**Website:** https://baserow.io/  
**Docs:** https://baserow.io/docs/  
**GitHub:** https://github.com/baserow/baserow  
**Docker image:** https://hub.docker.com/r/baserow/baserow  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set `BASEROW_PUBLIC_URL` to your Caddy hostname (e.g. `https://baserow.yourdomain.com`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Baserow listens on port `80` inside the container.
   - Put it behind Caddy on the `ingress-public` network, e.g.:
     - `https://baserow.yourdomain.com` → `baserow:80`
   - Create the first user on first visit.

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `baserow:80`)                                   |
| **Network** | `ingress-public` (for Caddy)                                                |
| **Images**  | `baserow/baserow:latest`                                                    |
| **Storage** | `baserow_data` (database and uploads)                                       |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `baserow.yourdomain.com` → `baserow:80` |

For Postgres, Redis, and scaling options, see the [official installation guide](https://baserow.io/docs/installation/install-with-docker-compose).

## Portainer

Add stack from this directory; set `BASEROW_PUBLIC_URL` in stack env. No host ports; use Caddy to expose the service.

## Updates and backups

Preserve the current image and private configuration, including legacy AI
provider environment values needed for rollback. Stop the all-in-one container
before copying its complete `baserow_data` volume, including PostgreSQL and
uploads. Verify an isolated restore with the previous
image and check database readability before updating. Startup can run application
migrations; verify users, tables, rows and uploads afterward. Restore the previous
image and complete data backup if preservation checks fail.


Baserow 2.4 imports supported legacy AI-provider settings into the database.
Manage imported instance providers in **Admin tools → AI providers**, and workspace
providers in **Settings → AI providers**; changing their old environment values
no longer updates them. Check the imported credentials, models and workspace
inheritance before removing rollback configuration. Database backups now include
these credentials and must remain private. Review skipped-provider fallbacks,
Kuma's separate model selection and published applications in the
[upstream migration guidance](https://baserow.io/docs/installation%2Fai-providers#upgrading-to-baserow-24).
Verify an isolated restore of the complete configuration and data before updating,
then verify provider settings and application data after migration.
