# OASIS

Self-hosted **file server** with user authentication, upload/download, search, previews (text, images, audio, video, PDF), media playlists, and shareable external links. Stack: Svelte frontend, Rust (Rocket) backend.

**Website / repo:** https://github.com/machengim/oasis  
**Docker image:** https://hub.docker.com/r/machengim/oasis  

## Quick start

1. Run `./prepare-stack.sh` (or copy `stack.env.example` → `stack.env` and `caddy_snippet.conf.example` → `caddy_snippet.conf`, then set your hostname in the Caddy snippet).
2. **Storage:** By default, files live in the named Docker volume `oasis-storage` (`/home/storage` in the container). To use a host directory, bind-mount it in `docker-compose.yml` instead of the `oasis-storage` volume (see `stack.env.example`).
3. Deploy: `docker compose up -d` from this directory (or add the stack in Portainer with the same compose).
4. Open the app via Caddy (e.g. `https://oasis.home` or `https://oasis.example.com`). Create the first user in the UI.

The upstream image listens on **port 8000** inside the container (`/opt/oasis/data` for app state, `/home/storage` for file library).

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; `reverse_proxy oasis:8000`) |
| **Network** | External `ingress-public` — same network as Caddy |
| **Image** | `machengim/oasis:latest` |
| **Env** | Optional TZ/locale via `../../shared.env`; no required vars in `stack.env` for defaults |
| **Volumes** | `oasis-data` → `/opt/oasis/data`; `oasis-storage` → `/home/storage` |

If the container **health check** stays unhealthy (image may lack `wget`), adjust or remove the `healthcheck` block in `docker-compose.yml` and rely on Uptime Kuma / Blackbox against the public URL.

## Caddy

This stack ships `caddy_snippet.conf.example` (placeholder `oasis.example.com`). After copying to `caddy_snippet.conf` and reloading Caddy, traffic routes to `oasis:8000`.

## Portainer

Stacks → Add stack → paste `docker-compose.yml`, set **env file** or duplicate `stack.env.example` into the stack environment, deploy. Ensure the stack attaches to the external network `ingress-public`.
