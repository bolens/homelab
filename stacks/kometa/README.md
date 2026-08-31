# Kometa

Kometa (formerly Plex Meta Manager) is a tool that automatically manages Plex library metadata, overlays, and collections.

**Website:** https://kometa.wiki
**Docs:** https://kometa.wiki/en/latest/
**GitHub:** https://github.com/Kometa-Team/Kometa

## Usage

Batch runner that connects to your Plex server and applies metadata config (collections, overlays, ratings)
on a schedule. Runs daily at 05:00 by default, then exits, not a persistent web service. Sits on the
dedicated `media-services` network alongside Plex and related stacks.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Create your Kometa config at the path specified by KOMETA_CONFIG_PATH (see Kometa docs for format).
3. Ensure the `media-services` external Docker network exists before deploying.
4. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| PUID | Yes | 1000 | Host UID for config file ownership |
| PGID | Yes | 1000 | Host GID for config file ownership |
| KOMETA_CONFIG_PATH | Yes | /home/youruser/.config/kometa | Host path to Kometa config directory |
| KOMETA_DATA_PATH | Yes | /home/youruser/.config/kometa/data | Host path to Kometa data directory |

## Notes

- TZ and locale come from shared.env.
- Healthcheck is disabled, Kometa runs and exits; the container will show as exited after each run.
- Plex URL and token must be set inside the Kometa config.yml, not here.
