# TRMNL Terminus

[Terminus](https://github.com/usetrmnl/terminus) is the self-hosted API and web backend for [TRMNL](https://usetrmnl.com/) e-paper devices. This stack runs the official image with PostgreSQL, Valkey (Redis-compatible), and a Sidekiq worker, matching the upstream [compose.yml](https://github.com/usetrmnl/terminus/blob/main/compose.yml) layout adapted for Caddy (no published host ports on the app or data stores).

**GitHub:** https://github.com/usetrmnl/terminus  
**Docker image:** `ghcr.io/usetrmnl/terminus:latest`

## Quick start

1. **Prepare**
   - Run `./prepare-stack.sh` (copies `stack.env.example` → `stack.env`, `caddy_snippet.conf.example` → `caddy_snippet.conf`, and copies `stack.env` → `.env` so Compose can interpolate variables in `docker-compose.yml`).
   - Edit `stack.env`: set `API_URI` to your public URL (e.g. `https://terminus.example.com`), generate `APP_SECRET` (`openssl rand -hex 32`), and set `DATABASE_PASSWORD` and `KEYVALUE_PASSWORD`.
   - If you change `HANAMI_PORT` from `2300`, update `caddy_snippet.conf` so `reverse_proxy` targets `terminus-web:<port>`.
   - Edit `caddy_snippet.conf`: replace `terminus.example.com` with your hostname.
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - HTTP listener is `HANAMI_PORT` inside the container (default `2300`). Caddy should reverse-proxy to `terminus-web:2300`.

## Configuration

| Item        | Details                                                                 |
| ----------- | ----------------------------------------------------------------------- |
| **Access**  | Via Caddy to `terminus-web` on `HANAMI_PORT`                            |
| **Network** | Web on `ingress-admin`; Postgres and Valkey internal only                     |
| **Storage** | `terminus_pg_data`, `terminus_keyvalue_data`, `terminus_web_uploads`, `terminus-certificates` |

An `terminus-init-certificates` one-shot container runs before the web service (same as upstream) to populate `/etc/ssl/certs` in the shared volume. Optional `CERTIFICATE_URLS` in `stack.env` adds extra CA PEMs.

## Portainer

Add stack from this directory; paste compose and set env vars from `stack.env.example`. No host ports; attach the external `ingress-admin` network and use Caddy to expose the app.
