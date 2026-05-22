# PocketBase

PocketBase is an open-source backend-as-a-service with a built-in SQLite database, auth, and admin UI.

**Website:** https://pocketbase.io
**Docs:** https://pocketbase.io/docs
**GitHub:** https://github.com/pocketbase/pocketbase

## Usage

PocketBase provides a REST/realtime API and admin dashboard for small apps and homelab projects.
Access the web UI and admin panel via Caddy at pocketbase.home or your configured public domain.
The image used is coollabsio/pocketbase (no official Docker image exists).

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Run `./prepare-stack.sh` to copy env and Caddy snippet files.
3. Add `caddy_snippet.conf` content to your Caddy stack config and reload Caddy.
4. On first visit to `/_/` (admin route) you will be prompted to create an admin account.
5. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| GOMEMLIMIT | No | (unset) | Go runtime memory limit, e.g. `256MiB` for constrained hosts |

## Notes

- There is no official PocketBase Docker image; this stack uses `coollabsio/pocketbase`.
- TZ and locale are provided by `shared.env`, not `stack.env`.
- Admin UI is at `http://<host>:8080/_/` before Caddy is configured.
