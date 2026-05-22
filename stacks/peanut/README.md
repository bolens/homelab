# PeaNUT

PeaNUT is a self-hosted web dashboard for monitoring UPS devices via Network UPS Tools (NUT).

**Website:** https://github.com/Brandawg93/PeaNUT
**GitHub:** https://github.com/Brandawg93/PeaNUT

## Usage

Connects to a NUT server on your network or localhost and displays real-time UPS status, battery
level, load, and runtime estimates in a web UI. Useful for monitoring power health in a homelab.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Set TZ to your local timezone.
3. Ensure a NUT server (upsd) is accessible from the container; configure the NUT host in the UI.
4. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| TZ | Yes | America/New_York | Timezone for the container |

## Notes

- PeaNUT does not run a NUT server itself — a separate NUT upsd instance is required.
- The web UI is served on port 3000 by default.
- NUT host, port, and credentials are configured in the PeaNUT web UI on first run.
