# InfluxDB

InfluxDB is an open-source time-series database optimized for storing metrics, events, and analytics data.

**Website:** https://www.influxdata.com
**GitHub:** https://github.com/influxdata/influxdb

## Usage

Central metrics store in a homelab monitoring stack. Receives data from Telegraf, Grafana Agent, or
direct writes and serves as a data source for Grafana dashboards. Runs on port 8086.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Set PUID/PGID to match your host user so data volume ownership is correct.
3. On first start, complete initial setup via the web UI at http://localhost:8086 to create org/bucket/token.
4. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| PUID | Yes | 1000 | Host UID for bind-mount file ownership |
| PGID | Yes | 1000 | Host GID for bind-mount file ownership |

## Notes

- TZ and locale come from shared.env.
- Save the operator token shown on first-run setup — it is not displayed again.
- InfluxDB 2.x uses a token-based auth model; clients need org, bucket, and token configured.
