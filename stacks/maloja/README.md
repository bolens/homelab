# Maloja

Maloja is a self-hosted music scrobble server that tracks your listening history and provides statistics.

**Website:** https://maloja.krateng.ch
**GitHub:** https://github.com/krateng/maloja

## Usage

Receives scrobbles from music players (via Last.fm-compatible API or native clients) and stores them
locally. Provides a web UI for listening stats, charts, and history. Typically proxied through Caddy
and optionally integrated with Last.fm/Spotify for metadata.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Set MALOJA_FORCE_PASSWORD (generate: `openssl rand -base64 24`), used for admin UI on first start.
3. Optionally add Spotify/Last.fm API keys for artwork and metadata enrichment.
4. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| MALOJA_FORCE_PASSWORD | Yes | None | Admin password set on first start |
| PUID | No | 1000 | Host UID for bind-mount file ownership |
| PGID | No | 1000 | Host GID for bind-mount file ownership |
| MALOJA_SPOTIFY_API_ID | No | None | Spotify app client ID for metadata |
| MALOJA_SPOTIFY_API_SECRET | No | None | Spotify app client secret for metadata |
| MALOJA_LASTFM_API_KEY | No | None | Last.fm API key for metadata |

## Notes

- TZ and locale come from shared.env.
- Application state and the scrobble database persist in `maloja_data`; include it in backups.
- API keys can also be configured in the Maloja admin UI after first start.
- Spotify credentials: https://developer.spotify.com/dashboard
- Last.fm credentials: https://www.last.fm/api/account/create
