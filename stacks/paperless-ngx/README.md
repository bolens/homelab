# Paperless-ngx

Document management: scan, OCR, and search your paperwork.

**Website:** https://docs.paperless-ngx.com  
**GitHub:** https://github.com/paperless-ngx/paperless-ngx

## Quick start

1. Set environment variables (required for reverse proxy and security):
   - **Portainer stack:** Add `PAPERLESS_URL` and `PAPERLESS_SECRET_KEY` (e.g. from `openssl rand -hex 32`) in the stack’s Environment.
   - **CLI / .env:** Copy `.env.example` to `.env` and set `PAPERLESS_URL` and `PAPERLESS_SECRET_KEY`.
2. Deploy: `docker compose up -d` or deploy the stack in Portainer.
3. Open via Caddy and create the initial admin user.

Config uses **named volumes** for export and consume (no bind-mounted `./export` or `./consume`), so the stack works when deployed from Portainer’s web editor.

## Configuration

| Item | Details |
|------|---------|
| **Port** | 8000 (proxied via Caddy only; no host port) |
| **Network** | `monitor` (external) — Caddy reverse-proxies to `paperless-ngx:8000` |
| **Image** | `ghcr.io/paperless-ngx/paperless-ngx:latest` |
| **Env** | `PAPERLESS_URL`, `PAPERLESS_SECRET_KEY` (set in stack or .env) |
| **Consume** | Named volume `consume` — add files via container/volume or bind mount override |

## Adding documents to consume (named volume)

To drop files into the consume volume from the host, either bind-mount a host directory in a one-off container and copy, or override the compose to use `./consume` when you deploy from a directory that has it.

## Start

From this directory: `docker compose up -d`. Or in Portainer: Stacks → Add stack → paste compose and set `PAPERLESS_URL` and `PAPERLESS_SECRET_KEY` in Environment.
