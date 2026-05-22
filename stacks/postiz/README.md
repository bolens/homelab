# Postiz

Postiz is an open-source social media scheduling and management platform supporting multiple networks.

**Website:** https://postiz.com
**GitHub:** https://github.com/gitroomhq/postiz-app

## Usage

Postiz lets you schedule and publish posts across social platforms from a single web UI.
It is typically accessed via a reverse proxy; configure Caddy or another proxy to reach the web UI.
Connect OAuth credentials for each social network you want to manage.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Run `./prepare-stack.sh` to copy env files.
3. Configure OAuth app credentials for your social platforms in the web UI after first login.
4. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| TZ | No | America/New_York | Container timezone |

## Notes

- First run will prompt you to create an admin account via the web UI.
- Postiz requires a database (Postgres) and Redis — check the generated compose for service dependencies.
