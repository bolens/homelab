# Asking

Lightweight self-hosted strawpoll-style polling app with a Next.js frontend and Node.js API backed by PostgreSQL.

**GitHub:** https://github.com/jdleo/asking

## Usage

Accessed via browser through a Caddy reverse proxy. The frontend and API run as separate containers sharing a PostgreSQL database. Set ASKING_PUBLIC_URL to your public hostname so generated poll links resolve correctly.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Set a strong POSTGRES_PASSWORD and update DATABASE_URI to match.
3. Set ASKING_PUBLIC_URL to your public hostname (must match Caddy config).
4. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| POSTGRES_USER | Yes | asking | PostgreSQL username |
| POSTGRES_PASSWORD | Yes | *** | PostgreSQL password (use openssl rand -hex 32) |
| POSTGRES_DB | Yes | asking | PostgreSQL database name |
| ASKING_PUBLIC_URL | Yes | https://poll.example.com | Public URL users access the app on |
| DIALECT | Yes | postgres | Sequelize DB dialect |
| DATABASE_URI | Yes | postgresql://asking:***@asking-db:5432/asking | Full Sequelize connection URI |

## Notes

- DATABASE_URI must use the same password as POSTGRES_PASSWORD.
- Caddy snippet is in caddy_snippet.conf; set your hostname there before deploying.
- The `repo/` directory contains the cloned source used to build images locally.
