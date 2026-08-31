# OpenSpeedTest

OpenSpeedTest is a self-hosted HTML5 network speed test tool that runs entirely in the browser.

**Website:** https://openspeedtest.com
**GitHub:** https://github.com/openspeedtest/Speed-Test

## Usage

Lightweight web server that serves a browser-based speed test for measuring LAN and WAN throughput
from any device without installing software. Useful for benchmarking network segments in a homelab.

## Setup

1. Run `./prepare-stack.sh`.
2. Replace the hostname in `caddy_snippet.conf`.
3. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| TZ | Yes | America/New_York | Timezone for the container |

## Notes

- Caddy uses the container's port 3000 HTTP endpoint; the image's separate
  port 3001 TLS listener is intentionally not exposed.
- Large uploads require the reverse proxy to accept request bodies of at least
  35 MB and use a timeout longer than 60 seconds.
- No authentication, restrict access via reverse proxy or firewall rules if needed.
- Results are not stored; this is a stateless, ephemeral test tool.
