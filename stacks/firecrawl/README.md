# Firecrawl

Web scraping and crawling API that converts any website into LLM-ready markdown or structured data.

- API docs: https://docs.firecrawl.dev/
- Self-hosting guide: https://github.com/firecrawl/firecrawl/blob/main/SELF_HOST.md
- Images: `ghcr.io/mendableai/firecrawl` + `mendableai/firecrawl-playwright-service`

## Services

| Container | Role | Port |
|---|---|---|
| firecrawl-api | REST API | 127.0.0.1:3002 |
| firecrawl-worker | Queue worker | — |
| firecrawl-playwright | Headless JS rendering | internal:3000 |
| firecrawl-redis | Job queue / rate limiting | internal |

## Setup

1. `cp stack.env.example stack.env`
2. Set `TEST_API_KEY` to a secret string (used as Bearer token)
3. Optionally set `OPENAI_API_KEY` if you want `llmExtract`
4. Deploy via Portainer or `docker compose up -d`
5. Copy `caddy_snippet.conf.example` → `caddy_snippet.conf` and adjust hostnames

## Authentication

`USE_DB_AUTHENTICATION=false` (default) — any client sending `TEST_API_KEY` as Bearer token is allowed.
For multi-user with per-key rate limiting, set `USE_DB_AUTHENTICATION=true` and configure Supabase.

## API usage

```bash
curl -X POST http://localhost:3002/v1/scrape \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "formats": ["markdown"]}'
```
