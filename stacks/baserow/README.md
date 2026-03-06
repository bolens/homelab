# Baserow – self-hosted Airtable alternative

[Baserow](https://baserow.io/) is an open-source no-code database and spreadsheet (tables, views, API). This stack runs Baserow with embedded SQLite; for production or heavy use you can switch to Postgres (see [Baserow Docker docs](https://baserow.io/docs/installation/install-with-docker-compose)). No host ports; put it behind Caddy.

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
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://baserow.yourdomain.com` → `baserow:80`
   - Create the first user on first visit.

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `baserow:80`)                                   |
| **Network** | `monitor` (for Caddy) + default                                             |
| **Images**  | `baserow/baserow:latest`                                                    |
| **Storage** | `baserow_data` (database and uploads)                                       |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `baserow.yourdomain.com` → `baserow:80` |

For Postgres, Redis, and scaling options, see the [official installation guide](https://baserow.io/docs/installation/install-with-docker-compose).

## Portainer

Add stack from this directory; set `BASEROW_PUBLIC_URL` in stack env. No host ports; use Caddy to expose the service.
