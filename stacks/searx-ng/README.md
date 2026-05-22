# SearXNG

Privacy-respecting metasearch engine. Aggregates results from multiple search engines.

**Website:** https://docs.searxng.org  
**Docs:** https://docs.searxng.org  
**GitHub:** https://github.com/searxng/searxng  
**Docker image:** https://hub.docker.com/r/searxng/searxng  
**Releases:** https://github.com/searxng/searxng/releases  

## Quick start

1. Run `./prepare-stack.sh` (creates `stack.env` and copies `settings.yml.example` to your configured `SEARXNG_SETTINGS_PATH` when missing).
2. Set a secret via environment (required). Generate and set `SEARXNG_SECRET` (see **Generating keys and secrets** below).
3. Set `SEARXNG_BASE_URL` in `stack.env` to the same HTTPS URL you use in Caddy (so result links and the UI resolve correctly).
4. Deploy: `docker compose --env-file stack.env up -d` (or deploy the stack in Portainer with the same variables).
5. Copy `caddy_snippet.conf.example` to your Caddy includes as `caddy_snippet.conf`, edit hostnames, then reload Caddy.
6. Access via Caddy at your public hostname (example: `https://search.example.com`).

## Generating keys and secrets

**SEARXNG_SECRET** (required) – used for signing. Generate:

```bash
openssl rand -hex 32
```

Set the output as `SEARXNG_SECRET` in `stack.env` or in the Portainer stack Environment.

Config is loaded from a host file path (`SEARXNG_SETTINGS_PATH`, default: `~/.config/searx-ng/settings.yml`) and bind-mounted to `/etc/searxng/settings.yml`. This keeps API/search settings (including JSON format for Perplexica) persistent across restarts and updates. Secret, base URL, and Redis URL are still set by environment variables.

## Configuration

| Item | Details |
|------|---------|
| **Port** | 8080 (proxied via Caddy) |
| **Network** | `monitor` — Caddy reverse-proxies to `searxng:8080` |
| **Image** | `searxng/searxng:latest` |
| **Config** | Bind mount `${SEARXNG_SETTINGS_PATH}` -> `/etc/searxng/settings.yml`; override secret/base URL/redis via env vars |

## Start

From this directory: `./prepare-stack.sh && docker compose --env-file stack.env up -d`.

## Portainer

- Preferred: **Stacks** → **Add stack** → **Repository**, compose path `stacks/searx-ng/docker-compose.yml`.
- On the Docker host, run `./prepare-stack.sh` first so `stack.env`, `caddy_snippet.conf`, and the host `settings.yml` exist.
- In Portainer’s stack environment, set at least `SEARXNG_SECRET`, `SEARXNG_BASE_URL` (public HTTPS URL), and `SEARXNG_SETTINGS_PATH` (absolute path on the host to `settings.yml`).
- Attach the stack to the external `monitor` network so Caddy can reach `searxng:8080`.
- Do not publish HTTP ports from this stack if Caddy is the front door.

## Backup

- Backup `${SEARXNG_SETTINGS_PATH}` (engine/search config) and Docker volumes `searxng_data`, `searxng_valkey_data`.
- Recommended cadence: weekly for config + cache snapshots, and before major SearXNG upgrades.
