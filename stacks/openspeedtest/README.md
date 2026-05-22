# OpenSpeedTest

OpenSpeedTest is a self-hosted HTML5 network speed test tool that runs entirely in the browser.

**Website:** https://openspeedtest.com
**GitHub:** https://github.com/openspeedtest/Speed-Test

## Usage

Lightweight web server that serves a browser-based speed test for measuring LAN and WAN throughput
from any device without installing software. Useful for benchmarking network segments in a homelab.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Set TZ to your local timezone.
3. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| TZ | Yes | America/New_York | Timezone for the container |

## Notes

- The speed test UI is served on port 3000 (HTTP) and 3001 (HTTPS) by default.
- No authentication — restrict access via reverse proxy or firewall rules if needed.
- Results are not stored; this is a stateless, ephemeral test tool.
