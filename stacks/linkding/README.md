# Linkding – lightweight bookmark manager

[Linkding](https://linkding.link/) is a simple, self-hosted bookmark manager with tags, full-text search, and import (Netscape bookmarks, etc.). This stack runs Linkding behind Caddy. No host ports; access via Caddy.

**Website:** https://linkding.link/  
**Docs:** https://linkding.link/installation  
**GitHub:** https://github.com/sissbruecker/linkding  
**Docker image:** https://hub.docker.com/r/sissbruecker/linkding  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Optionally set `TZ`.
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Linkding listens on port `9090` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://linkding.yourdomain.com` → `linkding:9090`
   - Create your user on first visit (no public signup by default; set via env if needed).

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `linkding:9090`)                                 |
| **Network** | `monitor` (for Caddy) + default                                             |
| **Images**  | `sissbruecker/linkding:latest`                                              |
| **Storage** | `linkding_data` (SQLite and uploads)                                        |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `linkding.yourdomain.com` → `linkding:9090` |

For optional env (e.g. `LD_HOST`, `LD_SERVER_PORT`, authentication), see [Linkding options](https://linkding.link/options/).

## Portainer

Add stack from this directory; ensure `stack.env` exists. No host ports; use Caddy to expose the service.
