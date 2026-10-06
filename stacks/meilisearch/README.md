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
2. **Existing databases:** follow [Upgrades](#upgrades) before changing the image.
3. **Deploy**

   ```bash
   docker compose up -d
   ```

4. **Access**
   - Meilisearch listens on port `7700` inside the container (HTTP API).
   - Put it behind Caddy on the `ingress-public` network, e.g.:
     - `https://meilisearch.yourdomain.com` → `meilisearch:7700`
   - Use the API to create indexes and search; see [Meilisearch docs](https://www.meilisearch.com/docs/learn/getting_started/quick_start).

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `meilisearch:7700`)                             |
| **Network** | `ingress-public` for Caddy/API clients                                      |
| **Images**  | Version and immutable digest in `docker-compose.yml`                                               |
| **Storage** | `meilisearch_data` (index data)                                             |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `meilisearch.yourdomain.com` → `meilisearch:7700` |

## Portainer

Add stack from this directory; set `MEILI_MASTER_KEY` when exposing publicly. No host ports; use Caddy to expose the service.

## Upgrades

An existing database needs an explicit migration when its Meilisearch version
changes. A plain image recreation does not perform this step. Follow the
[upstream migration guide](https://www.meilisearch.com/docs/resources/migration/updating)
and inspect the selected release notes before updating.

1. Record the running version/image, index settings, document counts and API keys.
   Create a snapshot or dump and wait for its task to succeed. Stop the instance
   for a consistent copy of `meilisearch_data` and runtime configuration.
2. Restore the copies in isolation and verify completeness and readability with
   the original image before touching the live volume. Test the selected version
   against another isolated copy using `--upgrade-db` (available since v1.51), or
   import a dump into an empty database. Retain the original volume and image.
3. Apply only the tested migration to the live search service. Use a temporary
   service command override for `--upgrade-db`; remove it after the migration.
   Never put the migration flag in the default command or delete the old database.
4. Check health, every index's settings/document count, representative searches
   and API-key access. If verification fails, stop the new image and restore the
   verified original database and compatible image. Remove only this operation's
   temporary copies after successful acceptance.
