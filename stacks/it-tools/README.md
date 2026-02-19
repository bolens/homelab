# IT Tools

Collection of handy online tools for developers, with great UX. A comprehensive set of utilities for developers and IT professionals.

**Website:** https://it-tools.tech  
**GitHub:** https://github.com/CorentinTh/it-tools

## Quick start

1. Deploy: `docker compose up -d`
2. Access: http://localhost:8080

## Configuration

| Item | Details |
|------|---------|
| **Port** | 8080 (mapped to container port 80) |
| **Network** | `monitor` — so monitoring tools can reach it |
| **Image** | `corentinth/it-tools:latest` |

## Features

IT Tools provides a wide range of developer utilities including:
- Text converters and formatters
- Hash generators
- Base64 encoders/decoders
- JSON formatters
- Color pickers
- QR code generators
- And many more...

## Alternative Images

You can also use the GitHub Container Registry image:
- `ghcr.io/corentinth/it-tools:latest`

## Start

From this directory: `docker compose up -d`.
