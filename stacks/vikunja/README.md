# Vikunja – tasks and lists

[Vikunja](https://vikunja.io/) is a self-hosted task and project manager (lists, kanban, Gantt, CalDAV). This stack runs Vikunja with SQLite behind Caddy. No host ports; access via Caddy.

**Website:** https://vikunja.io/  
**Docs:** https://vikunja.io/docs/  
**GitHub:** https://github.com/vikunja/vikunja  
**Docker image:** https://hub.docker.com/r/vikunja/vikunja  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set `VIKUNJA_SERVICE_PUBLICURL` to your Caddy URL with trailing slash (e.g. `https://vikunja.yourdomain.com/`).
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Vikunja listens on port `3456` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://vikunja.yourdomain.com` → `vikunja:3456`
   - Register the first user on first visit.

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `vikunja:3456`)                                 |
| **Network** | `monitor` (for Caddy) + default                                             |
| **Images**  | `vikunja/vikunja:latest`                                                    |
| **Storage** | `vikunja_data` (SQLite DB and uploads)                                       |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `vikunja.yourdomain.com` → `vikunja:3456` |

For Postgres, Redis, or CalDAV, see [Vikunja full Docker example](https://vikunja.io/docs/full-docker-example/).

## Portainer

Add stack from this directory; set `VIKUNJA_SERVICE_PUBLICURL` in stack env. No host ports; use Caddy to expose the service.
