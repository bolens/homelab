# Beszel

Lightweight server monitoring with Docker/Podman stats, historical metrics, and alerts. The **hub** is the web UI and API; **agents** run on each host you want to monitor ([Beszel](https://beszel.dev/), [GitHub](https://github.com/henrygd/beszel)).

**Website:** https://beszel.dev/  
**Docs:** https://beszel.dev/guide/getting-started  
**GitHub:** https://github.com/henrygd/beszel  
**Docker Hub:** https://hub.docker.com/r/henrygd/beszel  

## Quick start

1. Run `./prepare-stack.sh` (creates `stack.env` if missing, ensures `BESZEL_DATA_DIR`, copies `stack.env` → `.env` for compose interpolation).
2. Edit `stack.env`: set **`BESZEL_APP_URL`** to the same URL you will use in the browser (e.g. `https://beszel.example.com`), matching your Caddy hostname.
3. Copy `caddy_snippet.conf.example` → `caddy_snippet.conf`, replace `beszel.example.com` with your domain, reload Caddy.
4. Start: `docker compose up -d` from this directory (or deploy as a stack in Portainer).
5. Open the hub URL, create an admin user, then add systems from the UI. For agents on **other** hosts, install the agent per [Agent installation](https://beszel.dev/guide/agent-installation) and point `HUB_URL` at your public hub URL.

## Hub + agent on the same Docker host

This stack runs **only the hub**. The upstream docs show a second service, `beszel-agent`, with `network_mode: host`, a shared Unix socket volume, and `docker.sock` for local Docker stats. If you want that on the same machine, add a `docker-compose.override.yml` (gitignored) or follow [Hub installation – Docker](https://beszel.dev/guide/hub-installation): mount `./beszel_socket` on the hub, run `henrygd/beszel-agent` with `LISTEN`, `HUB_URL`, `TOKEN`, and `KEY` from the UI, and use the socket path as Host/IP when adding the system.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `beszel:8090`) |
| **Data** | `BESZEL_DATA_DIR` (default `~/.local/share/beszel`) → `/beszel_data` |
| **Public URL** | `BESZEL_APP_URL` — required; must match how users reach the hub (links, OAuth, agents) |
| **Network** | `ingress-admin` — shared with Caddy |
| **Health** | `GET /api/health` (see [Healthchecks](https://beszel.dev/guide/healthchecks)) |

Env reference: [ENV-VARS.md](../../documents/ENV-VARS.md). TZ/locale: [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

## OAuth / OIDC

Beszel supports OAuth2 providers and can disable password login; configure in the hub UI after first setup. See [Beszel authentication](https://beszel.dev/) and the guide.

## Start

`docker compose up -d` from this directory.
