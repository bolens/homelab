# RomM

Self-hosted ROM manager: scan, enrich with metadata, browse, and play games in the browser via EmulatorJS. Supports 400+ platforms, multi-disk games, mods, and optional metadata from IGDB, Screenscraper, MobyGames, SteamGridDB, and RetroAchievements.

**Homepage:** https://romm.app  
**Docs:** https://docs.romm.app/latest/  
**GitHub:** https://github.com/rommapp/romm  
**Docker:** https://hub.docker.com/r/rommapp/romm  

Access via Caddy at **https://romm.yourdomain.com** (or your configured hostname).

## Quick start

1. **Config**
   - Copy `stack.env.example` → `stack.env`.
   - Set `ROMM_AUTH_SECRET_KEY` (e.g. `openssl rand -hex 32`), `MARIADB_ROOT_PASSWORD`, `MARIADB_PASSWORD`, and `ROMM_BASE_URL` to match your Caddy hostname.
   - RomM requires a `config.yml` in its config directory. Copy the [upstream example](https://github.com/rommapp/romm/blob/master/examples/config.example.yml) into the `romm_config` volume after first run, or bind-mount a host directory (see **Library and config** below).
2. **Deploy:** From the stack directory run `docker compose up -d`.
3. **First run:** Create an admin user in the web UI. Then add `config.yml` to `/romm/config` (e.g. `docker cp config.yml romm:/romm/config/`) or bind-mount your config and restart.
4. **Library:** By default the stack uses a named volume `romm_library` for ROMs. For large collections, bind-mount a host path in `docker-compose.yml` (e.g. `- /path/to/your/roms:/romm/library`) and follow RomM’s [folder structure](https://docs.romm.app/latest/Getting-Started/Folder-Structure/).

**Portainer:** Add stack → paste `docker-compose.yml` → set env vars from `stack.env` (or mount `stack.env`). Ensure `config.yml` is present in the config volume or bind-mounted before relying on scans.

## Library and config

- **Library:** Default path inside the container is `/romm/library`. The default compose uses a named volume `romm_library`. To use a host directory instead, replace the `romm_library` volume with a bind mount, e.g. `- /path/to/roms:/romm/library`. Ensure the host path is readable and writable by the container user (rommapp/romm typically runs as UID 1000); e.g. `chown -R 1000:1000 /path/to/roms` if needed.
- **Config:** RomM expects `config.yml` at `/romm/config/config.yml`. After first start you can copy a file in: `docker cp config.example.yml romm:/romm/config/config.yml`, or add a bind mount for the config directory and place `config.yml` there.
- **Assets:** Saves and other assets are stored in the `romm_assets` volume (or bind-mount a path to `/romm/assets`).

## Secrets

Generate and set in `stack.env` (do not commit):

```bash
# ROMM_AUTH_SECRET_KEY
openssl rand -hex 32

# MariaDB passwords (use different values for root and app user)
openssl rand -base64 24
```

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `romm:8080`) |
| **Network** | `romm` (internal DB); `monitor` (Caddy) |
| **Images** | `rommapp/romm:latest`, `mariadb:11` |
| **Env (required)** | `ROMM_AUTH_SECRET_KEY`, `MARIADB_ROOT_PASSWORD`, `MARIADB_PASSWORD`, `ROMM_BASE_URL` |
| **Env (optional)** | `TZ`; metadata API keys (IGDB, Screenscraper, etc.) – see [RomM env docs](https://docs.romm.app/latest/Getting-Started/Environment-Variables/) |
| **Storage** | Named volumes: `romm_mysql_data`, `romm_resources`, `romm_data`, `romm_config`, `romm_library`, `romm_assets`; optionally bind-mount library/config/assets |

## Caddy reverse proxy

Add a site block for the RomM hostname (e.g. `romm.yourdomain.com`):

```
romm.yourdomain.com {
	reverse_proxy romm:8080
}
```

Use the same hostname in `ROMM_BASE_URL`.

## Health and monitoring

RomM does not expose a dedicated health endpoint. Use a generic HTTP check to the app URL (e.g. `https://romm.yourdomain.com`) in Uptime Kuma.

## Optional: metadata providers

For richer metadata and artwork, sign up for API keys and add them to `stack.env` (see [RomM metadata providers](https://docs.romm.app/latest/Getting-Started/Metadata-Providers/)): IGDB, Screenscraper, MobyGames, SteamGridDB, RetroAchievements.
