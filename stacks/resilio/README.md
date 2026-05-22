# Resilio Sync

Resilio Sync (formerly BitTorrent Sync) is a peer-to-peer file synchronization tool for homelab and private file sharing.

**Website:** https://www.resilio.com/individuals/
**GitHub:** https://github.com/linuxserver/docker-resilio-sync

## Usage

Resilio Sync keeps folders synchronized across multiple devices without a central cloud server.
The web UI (port 8888) is exposed via Caddy at resilio.home / resilio.local or your configured domain.
Add sync folders through the UI and share keys/links with other devices.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Run `./prepare-stack.sh` to copy env and Caddy snippet files.
3. Add `caddy_snippet.conf` content to your Caddy stack config and reload Caddy.
4. Set `PUID`/`PGID` to match your host user (`id -u` / `id -g`).
5. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| PUID | Yes | 1000 | Host user ID for file ownership |
| PGID | Yes | 1000 | Host group ID for file ownership |
| UMASK | No | 022 | File permission umask |

## Notes

- TZ/locale are provided by `shared.env`.
- Resilio Free tier limits folder count; a Business/Pro license unlocks more features.
- Ensure sync ports (default 55555) are open in firewall for LAN/WAN peer discovery.
