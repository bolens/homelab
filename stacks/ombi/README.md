# Ombi

Ombi is a self-hosted media request and user management tool for Plex, Jellyfin, and Emby.

**Website:** https://ombi.io
**Docs:** https://docs.ombi.app
**GitHub:** https://github.com/Ombi-app/Ombi

## Usage

Provides a web UI where users can request new movies and TV shows, which are forwarded to Radarr/Sonarr
for automatic download. Typically proxied through Caddy and connected to your media server and *arr
stacks over an internal Docker network.

## Setup

1. Copy `stack.env.example` to `stack.env` — no required variables beyond shared.env defaults.
2. On first start, complete the web setup wizard to connect Plex/Jellyfin and Radarr/Sonarr.
3. Deploy: `docker compose up -d`

No required environment variables (TZ/locale come from shared.env).

## Notes

- Ombi stores its config in a SQLite database inside the config volume — back it up regularly.
- Notification integrations (email, Discord, etc.) are configured entirely within the web UI.
- Consider Jellyseerr as an alternative if your media server is Jellyfin-only.
