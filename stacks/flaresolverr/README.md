# FlareSolverr

Proxy server that solves Cloudflare and DDoS-GUARD browser challenges and returns HTML, cookies, and user-agent for use with other HTTP clients (for example *arr indexers or Jackett).

**GitHub:** https://github.com/FlareSolverr/FlareSolverr  
**Container registry:** https://github.com/orgs/FlareSolverr/packages/container/package/flaresolverr  
**Docker Hub mirror:** https://hub.docker.com/r/flaresolverr/flaresolverr  

## Quick start

1. **Networks:** Ensure the external `media-automation` network exists (see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md)).
2. **Prepare files:** From this directory run `./prepare-stack.sh` (copies `stack.env.example` → `stack.env` and `caddy_snippet.conf.example` → `caddy_snippet.conf` when missing).
3. **Deploy**
   ```bash
   docker compose up -d
   ```
4. **Check:** `curl -sf http://flaresolverr:8191/health` from a container on `media-automation`.

**Portainer:** Stacks → Add stack → paste `docker-compose.yml`, set env from `stack.env.example`, deploy.

## Configuration

| Item | Details |
|------|---------|
| **Access** | *arr/Jackett use `http://flaresolverr:8191` on `media-automation` (no host port). |
| **API** | `POST /v1` with JSON body (`cmd`, `url`, `maxTimeout`, etc.). See upstream README. |
| **Health** | `GET /health` (JSON). |
| **Image** | `ghcr.io/flaresolverr/flaresolverr:latest` |
| **Storage** | `flaresolverr_config` → `/config` (optional `LOG_FILE` under `/config`). |

### Integrations

- **Prowlarr / Jackett / Sonarr / Radarr:** Configure the FlareSolverr URL as `http://flaresolverr:8191` (or your public Caddy URL if clients are not on Docker networks).
- **RAM:** Each solving request can launch Chromium; avoid high concurrency on small hosts.

### Caddy reverse proxy

Example vhosts live in `caddy_snippet.conf.example` (placeholder hostnames). Import the generated `caddy_snippet.conf` from the main Caddy stack.

If the service is reachable from the internet, treat it as sensitive (no built-in auth): use Cloudflare Access or restrict who can reach the hostname.

## Environment variables

See `stack.env.example` and the [upstream environment table](https://github.com/FlareSolverr/FlareSolverr#environment-variables). Notable options: `LOG_LEVEL`, `PROXY_URL`, `PROMETHEUS_ENABLED`, `PROMETHEUS_PORT` (default 8192; scrape `http://flaresolverr:8192/metrics` when enabled).
