# Seerr

[Seerr](https://seerr.dev/) is an open-source media discovery and request manager. It works with **Jellyfin**, **Plex**, or **Emby**, and forwards approved requests to **Radarr** and **Sonarr**.

**Website:** https://seerr.dev/  
**Docs:** https://docs.seerr.dev/  
**GitHub:** https://github.com/seerr-team/seerr  
**Container image:** https://github.com/seerr-team/seerr/pkgs/container/seerr  

## `/app/config` bind mount (required for official image)

The image treats a sentinel file **`config/DOCKER`** (present on the default Docker volume layout) as “not bind-mounted”. A **host directory** mounted at **`/app/config`** avoids:

> The /app/config volume mount was not configured properly…

This stack mounts **`SEERR_CONFIG_PATH`** → **`/app/config`** (default **`~/.config/seerr`**). If you **copied** data from an old named volume, remove the sentinel and restart or the warning persists:

```bash
sudo rm -f "${SEERR_CONFIG_PATH:-$HOME/.config/seerr}/DOCKER"
docker compose --env-file stack.env restart seerr
```

## Quick start

1. Run `./prepare-stack.sh` (or copy `stack.env.example` → `stack.env` and `caddy_snippet.conf.example` → `caddy_snippet.conf`).
2. Edit `caddy_snippet.conf` with your real hostname(s).
3. **Migrating from the old named volume only:** if you previously used Compose volume `seerr_config`, copy data once before switching (adjust names with `docker volume ls | grep seerr`):

   ```bash
   mkdir -p ~/.config/seerr
   docker run --rm -v seerr_seerr_config:/from:ro -v "$HOME/.config/seerr:/to" alpine cp -a /from/. /to/
   sudo rm -f "$HOME/.config/seerr/DOCKER"
   ```

4. From this directory:
   ```bash
   docker compose --env-file stack.env up -d
   ```
5. Open the app via Caddy, complete the setup wizard, and add your media server and *arr instances. Use internal URLs on the shared `monitor` network, for example:
   - Jellyfin: `http://jellyfin:8096`
   - Plex: `http://plex:32400` (see Plex stack docs for token/claim)
   - Radarr: `http://radarr:7878`
   - Sonarr: `http://sonarr:8989`

**Portainer:** Stacks → Add stack → paste `docker-compose.yml`, set env from `stack.env.example` (use **absolute** `SEERR_CONFIG_PATH`), attach to external network `monitor`, deploy.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host ports; reverse-proxy to `seerr:5055`) |
| **Network** | `monitor` (required so Caddy and other stacks can reach Seerr) |
| **Image** | `ghcr.io/seerr-team/seerr:latest` (pin a `vX.Y.Z` tag for reproducible deploys) |
| **Storage** | `SEERR_CONFIG_PATH` (default `${HOME}/.config/seerr`) → `/app/config` (SQLite by default; see [database options](https://docs.seerr.dev/extending-seerr/database-config)) |
| **Process user** | Runs as UID **1000** (`node`). If you bind-mount config instead of the named volume, `chown -R 1000:1000` that path. |

Set the **public URL** in Seerr’s settings to match the URL users use (e.g. `https://seerr.example.com`) so OAuth and links work behind Caddy.

## Caddy reverse proxy

See `caddy_snippet.conf.example` (placeholder `seerr.example.com`). The main Caddy stack imports `stacks/*/caddy_snippet.conf`.

## Dependencies

- **Caddy** stack for HTTPS and hostname routing.
- Optional but typical: **Jellyfin**, **Plex**, or **Emby**; **Radarr** / **Sonarr** on the same Docker host and `monitor` network.

For outbound email notifications, point Seerr at your SMTP relay (e.g. Postfix `smtp-relay` on `monitor`) from the Seerr UI.
