# camofox-browser

Anti-detection browser server for AI agents. Wraps Camoufox (a Firefox fork with
C++-level fingerprint spoofing) in a REST API. Accessibility snapshots, stable element
refs, session isolation, proxy support.

- Repo: https://github.com/jo-inc/camofox-browser
- Image: ghcr.io/jo-inc/camofox-browser:latest

## Services

| Container | Role | Port |
|---|---|---|
| camofox-browser | REST API + headless Firefox | 127.0.0.1:9377 |

## Setup

1. cp stack.env.example stack.env
2. Optionally set CAMOFOX_ACCESS_KEY to protect the API
3. docker compose up -d
4. Copy caddy_snippet.conf.example to caddy_snippet.conf if you want a hostname

## Quick test

curl http://localhost:9377/health

## API usage (accessibility snapshot)

curl -X POST http://localhost:9377/session \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# With access key:
curl -X POST http://localhost:9377/session \
  -H "Authorization: Bearer <CAMOFOX_ACCESS_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

## Notes

- shm_size=512mb is set to prevent browser crashes under load.
- Named volumes persist cookies, session profiles, and trace zips across restarts.
- Telemetry is enabled by default; set CAMOFOX_CRASH_REPORT_ENABLED=false to opt out.
