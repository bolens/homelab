# Postgres backup (homelab) 🗄️

**Goal:** be able to restore `asking-ng` poll data after disk loss or a bad upgrade.

## Volume

Production Compose typically persists Postgres in a named volume (see `docker-compose.yml`, e.g. `asking_ng_pg_data`). That volume is **not** in your git tree.

## Logical dump (recommended)

From the host (replace container name if yours differs):

```bash
docker exec -t asking-ng-db-1 pg_dump -U asking asking | gzip -1 > asking-ng-$(date -u +%Y%m%dT%H%MZ).sql.gz
```

Restore (destructive — drops into an empty DB or new volume):

```bash
gunzip -c asking-ng-YYYYMMDDTHHMMZ.sql.gz | docker exec -i asking-ng-db-1 psql -U asking asking
```

## RPO / RTO

- **RPO:** how often you run `pg_dump` (hourly cron vs weekly).
- **RTO:** time to recreate the stack, restore the dump, and re-point Caddy if needed.

## Related

- Creator/streamer roadmap (future ideas): [CREATOR-STREAMER-ROADMAP.md](CREATOR-STREAMER-ROADMAP.md)
