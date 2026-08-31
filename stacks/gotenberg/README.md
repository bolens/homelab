# Gotenberg

Gotenberg is a stateless API microservice for converting HTML, Markdown, Office documents, and URLs to PDF using headless Chrome and LibreOffice.

**Website:** https://gotenberg.dev
**Docs:** https://gotenberg.dev/docs/getting-started/introduction
**GitHub:** https://github.com/gotenberg/gotenberg

## Usage

Used as an internal service called by other stacks (e.g., Paperless-ngx, custom apps) via HTTP API on port 3000. No browser UI; all interaction is via REST API calls or Caddy proxy. Accessible on the shared Docker network.

## Setup

1. Run `./prepare-stack.sh`.
2. Review the optional timezone settings.
3. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| TZ | No | America/New_York | Container timezone |

## Notes

- Gotenberg is stateless, no persistent storage needed.
- This stack is internal-only by default and has no Caddy route or host port.
- Health is checked through Gotenberg's `/health` endpoint.
- Paperless-ngx can use Gotenberg for document conversion; set PAPERLESS_TIKA_GOTENBERG_ENDPOINT accordingly.
- Default API port is 3000; no authentication is built in, restrict network access.
