# Tautulli

Tautulli is a monitoring and statistics tracker for Plex Media Server.

**Website:** https://tautulli.com
**GitHub:** https://github.com/Tautulli/Tautulli

## Usage

Tautulli tracks Plex playback history, user activity, and library statistics via a web UI on port 8181.
Access it through Caddy at tautulli.home / tautulli.local or your configured public domain.
Point Tautulli at your Plex server during initial setup to connect the two stacks.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Run `./prepare-stack.sh` to copy env and Caddy snippet files.
3. Add `caddy_snippet.conf` content to your Caddy stack config and reload Caddy.
4. Set `PUID`/`PGID` to match your host user and set config/data paths.
5. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| PUID | Yes | 1000 | Host user ID for file ownership |
| PGID | Yes | 1000 | Host group ID for file ownership |
| TAUTULLI_CONFIG_PATH | Yes | `${HOME}/.config/tautulli` | Host path for Tautulli config |

## Notes

- TZ/locale are provided by `shared.env`.
- On first launch, complete the setup wizard and provide your Plex URL and token.
- Tautulli must be able to reach your Plex server; ensure they share a Docker network or use host IP.
- The `/config` bind mount contains the database and settings and should be
  included in backups.
