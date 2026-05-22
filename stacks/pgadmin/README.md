# pgAdmin

pgAdmin 4 is the leading open-source web-based administration and development platform for PostgreSQL.

**Website:** https://www.pgadmin.org
**Docs:** https://www.pgadmin.org/docs/
**GitHub:** https://github.com/pgadmin-org/pgadmin4

## Usage

Provides a browser-based GUI for managing PostgreSQL databases, running queries, and inspecting schemas.
Typically proxied through Caddy and used to administer Postgres containers on internal Docker networks.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Set PGADMIN_DEFAULT_EMAIL (your login email) and PGADMIN_DEFAULT_PASSWORD (generate: `openssl rand -base64 24`).
3. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| PGADMIN_DEFAULT_EMAIL | Yes | admin@example.com | Email address used to log in to pgAdmin |
| PGADMIN_DEFAULT_PASSWORD | Yes | — | Password for the pgAdmin web UI login |

## Notes

- TZ and locale come from shared.env.
- Server connections are added inside the pgAdmin UI; credentials are stored in its internal database.
- pgAdmin data (saved servers, preferences) persists in a named volume — back it up before upgrades.
