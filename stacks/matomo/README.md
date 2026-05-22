# Matomo

Matomo is a self-hosted, privacy-respecting web analytics platform that gives you full ownership of your data.

**Website:** https://matomo.org
**Docs:** https://matomo.org/docs/
**GitHub:** https://github.com/matomo-org/matomo

## Usage

Tracks visitor analytics for self-hosted websites without sending data to third parties. Runs with a
MariaDB backend and is proxied through Caddy. Add the Matomo JS tracker snippet to your sites and
configure periodic archiving via the built-in cron job.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Set MATOMO_DB_PASSWORD and MATOMO_DB_ROOT_PASSWORD (generate: `openssl rand -hex 32`).
3. Set MATOMO_BASE_URL to your Caddy hostname (e.g. https://matomo.example.com).
4. On first start, complete the web installer at your Matomo URL.
5. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| MATOMO_DB_NAME | Yes | matomo | MariaDB database name |
| MATOMO_DB_USER | Yes | matomo | MariaDB user for Matomo |
| MATOMO_DB_PASSWORD | Yes | — | MariaDB password (generate with openssl) |
| MATOMO_DB_ROOT_PASSWORD | No | — | MariaDB root password for direct DB access |
| MATOMO_CONFIG_PATH | Yes | — | Host path to matomo config.ini.php |
| MATOMO_BASE_URL | Yes | — | Base URL used by the archiving cron job |
| MATOMO_ARCHIVE_INTERVAL_SECONDS | No | 3600 | How often the archive cron runs (seconds) |

## Notes

- TZ and locale come from shared.env.
- The web installer creates config.ini.php; MATOMO_CONFIG_PATH must point to that file for persistence.
- Archiving keeps reports fast; without it, reports are generated on-demand which is slow at scale.
