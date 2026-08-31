# PeaNUT

PeaNUT is a self-hosted web dashboard for monitoring UPS devices via Network UPS Tools (NUT).

**Website:** https://github.com/Brandawg93/PeaNUT
**GitHub:** https://github.com/Brandawg93/PeaNUT

## Usage

Connects to a NUT server on your network or localhost and displays real-time UPS status, battery
level, load, and runtime estimates in a web UI. Useful for monitoring power health in a homelab.

## Setup

1. Run `./prepare-stack.sh`.
2. Set `PUID`, `PGID`, and `PEANUT_CONFIG_PATH`; ensure the directory is
   writable by that UID/GID.
3. Replace the hostname in `caddy_snippet.conf`.
4. Ensure a NUT server is reachable and deploy with `docker compose up -d`.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| PUID / PGID | Yes | 1000 | UID/GID that owns the config directory |
| PEANUT_CONFIG_PATH | Yes | `${HOME}/.config/peanut` | Persistent settings path |
| WEB_USERNAME / WEB_PASSWORD | No | unset | Optional initial account |

## Notes

- PeaNUT does not run a NUT server itself, a separate NUT upsd instance is required.
- Current PeaNUT releases serve the web UI on port 8080.
- NUT host, port, and credentials are configured in the PeaNUT web UI on first run.
- `/api/ping` is used for the container healthcheck.
