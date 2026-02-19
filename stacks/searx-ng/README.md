# SearXNG

Privacy-respecting metasearch engine. Aggregates results from multiple search engines.

**Website:** https://docs.searxng.org  
**GitHub:** https://github.com/searxng/searxng

## Quick start

1. Set a secret via environment (required):
   - **Portainer stack:** Add env var `SEARXNG_SECRET` in the stack (e.g. value from `openssl rand -hex 32`).
   - **CLI / .env:** Copy `.env.example` to `.env` and set `SEARXNG_SECRET` (and optionally `SEARXNG_BASE_URL`).
2. Deploy: `docker compose up -d` or deploy the stack in Portainer.
3. Access via Caddy: https://searx-ng.home (or your configured hostname)

Config is stored in a **named volume** (`searxng_config`), so the stack works when deployed from Portainer’s web editor (no bind-mounted `searxng/` folder needed). Secret, base URL, and Redis URL are set by environment variables.

## Configuration

| Item | Details |
|------|---------|
| **Port** | 8080 (proxied via Caddy) |
| **Network** | `monitor` — Caddy reverse-proxies to `searxng:8080` |
| **Image** | `searxng/searxng:latest` |
| **Config** | Named volume `searxng_config`; override via `SEARXNG_SECRET`, `SEARXNG_BASE_URL`, `SEARXNG_REDIS_URL` |

## Optional: bind-mount config (e.g. from Git)

If you deploy from a directory that has a `searxng/` folder (e.g. this repo) and want to edit `settings.yml` on the host, replace the config volume in `docker-compose.yml` with:

```yaml
- ./searxng:/etc/searxng:ro
```

and remove the `searxng_config` volume and its entry under `volumes:`.

## Start

From this directory: `docker compose up -d`. Or in Portainer: Stacks → Add stack → paste compose and set `SEARXNG_SECRET` in Environment.
