# Meilisearch – search engine

[Meilisearch](https://www.meilisearch.com/) is a fast, typo-tolerant search engine with an HTTP API. Use it as a search backend for your apps or custom UIs. This stack runs Meilisearch behind Caddy. No host ports; access via Caddy.

**Website:** https://www.meilisearch.com/  
**Docs:** https://www.meilisearch.com/docs/  
**GitHub:** https://github.com/meilisearch/meilisearch  
**Docker image:** https://hub.docker.com/r/getmeili/meilisearch  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - When exposing via Caddy, set `MEILI_MASTER_KEY` (e.g. `openssl rand -hex 32`) and `MEILI_ENV=production`.
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Meilisearch listens on port `7700` inside the container (HTTP API).
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://meilisearch.yourdomain.com` → `meilisearch:7700`
   - Use the API to create indexes and search; see [Meilisearch docs](https://www.meilisearch.com/docs/learn/getting_started/quick_start).

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `meilisearch:7700`)                             |
| **Network** | `monitor` (for Caddy) + default                                             |
| **Images**  | `getmeili/meilisearch:latest`                                               |
| **Storage** | `meilisearch_data` (index data)                                             |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `meilisearch.yourdomain.com` → `meilisearch:7700` |

## Portainer

Add stack from this directory; set `MEILI_MASTER_KEY` when exposing publicly. No host ports; use Caddy to expose the service.
