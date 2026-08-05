# IT Tools

Collection of handy online tools for developers, with great UX. A comprehensive set of utilities for developers and IT professionals.

**Website:** https://it-tools.tech  
**Docs:** https://github.com/sharevb/it-tools#readme
**GitHub:** https://github.com/sharevb/it-tools
**Docker image:** https://github.com/sharevb/it-tools/pkgs/container/it-tools
**Releases:** https://github.com/sharevb/it-tools/releases

## Quick start

1. Deploy: `docker compose up -d`
2. Access via Caddy (e.g. https://it-tools.yourdomain.com). No host port is exposed; the stack is on the dedicated `ingress-admin` network.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `it-tools:8080`) |
| **Network** | `ingress-admin` — dedicated Caddy-to-service ingress |
| **Image** | Maintained fork `ghcr.io/sharevb/it-tools:2026.7.11` |

## Features

IT Tools provides a wide range of developer utilities including:
- Text converters and formatters
- Hash generators
- Base64 encoders/decoders
- JSON formatters
- Color pickers
- QR code generators
- And many more...

## Start

From this directory: `docker compose up -d`.
