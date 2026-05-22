# The Lounge

The Lounge is a self-hosted, always-on IRC web client with persistent connection and multi-user support.

**Website:** https://thelounge.chat
**Docs:** https://thelounge.chat/docs
**GitHub:** https://github.com/thelounge/thelounge

## Usage

The Lounge keeps you connected to IRC servers even when your browser is closed, logging all messages.
Access the web UI (port 9000) via Caddy at thelounge.home / thelounge.local or your public domain.
Multiple users can each have their own IRC networks and channels configured through the UI.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Run `./prepare-stack.sh` to copy env and Caddy snippet files.
3. Add `caddy_snippet.conf` content to your Caddy stack config and reload Caddy.
4. Create the first user: `docker compose exec thelounge thelounge add <username>`
5. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| THELOUNGE_PUBLIC | No | false | Enable public mode (no auth); not recommended |
| THELOUNGE_PORT | No | 9000 | Internal listen port |

## Notes

- TZ/locale are provided by `shared.env`.
- Default mode is private (authentication required); leave `THELOUNGE_PUBLIC` unset.
- User accounts are managed via the `thelounge` CLI inside the container.
