# Dawarich

Store and explore personal location history, trips, and photo memories.

**Website:** https://dawarich.app/
**Docs:** https://dawarich.app/docs/
**GitHub:** https://github.com/Freika/dawarich

## Prepare and deploy

1. Run `./prepare-stack.sh`. It preserves existing files, ensures external networks, synchronizes `stack.env` to `.env`, and never starts containers.
2. Edit the private `stack.env`. Create the first local account through the private route before enabling public ingress.
3. Review `caddy_snippet.conf`, replace placeholder hostnames, and import it into Caddy only after authentication is ready.
4. Validate and deploy explicitly:

   ```bash
   docker compose --env-file stack.env config --quiet
   docker compose --env-file stack.env up -d
   docker compose ps
   ```

## Access and persistence

Caddy on `ingress-sensitive`, upstream `dawarich:3000`. No host port is published.

- `dawarich_public` at `/var/app/public`.
- `dawarich_watched` at `/var/app/tmp/imports/watched`.
- `dawarich_storage` at `/var/app/storage`.

Images are pinned by version and digest in Compose. Configure timezone through `stack.env`. The generated catalog metadata is in `stack.yaml`.

## Initial setup and location data

Generate POSTGRES_PASSWORD and a stable SECRET_KEY_BASE before first deployment. Set APPLICATION_HOSTS to the exact allowed public/local names. Complete onboarding and replace any upstream bootstrap credentials before public access. Pair a location source such as OwnTracks, the Dawarich mobile app, or a supported export. Immich integration requires its own restricted API key and an application-reachable URL. Location collection and photo access are explicit operator choices.

The stack follows upstream 1.21.0 with embedded Sidekiq in the app process, PostGIS 17, and Redis 8. The database is private to this project and is not mounted into the web container. Back up Postgres with a consistent dump plus public, watched, storage, and Redis volumes and the stable application secret. Restore to an isolated matching PostGIS instance and verify record counts and imports before replacing live data.

## Verification, upgrades, and recovery

Check container health, open the application through its intended route, and complete an authenticated application operation. A passing health probe does not prove onboarding, external provider access, notification delivery, or device playback.

Before upgrades, record the exact image and configuration and back up all declared persistent volumes and private environment files with writers quiesced or application-consistent methods. Restore copies in isolation and verify database integrity, file hashes, and representative records. Preserve credentials and encryption keys with their matching data. Do not assume an older image can read an upgraded database. If verification fails, stop the changed service and restore verified state with the original compatible image. Never use `docker compose down -v` during routine maintenance.

The example retains PostgreSQL 17 with PostGIS 3.5. Moving to PostGIS 3.6 also requires an extension migration; replacing the image does not upgrade existing databases. First rehearse on an isolated, verified restore: record `postgis_full_version()` in every database using PostGIS, update its binaries, run `SELECT postgis_extensions_upgrade();`, and verify `postgis_full_version()` again together with geometry/SRID checks, record counts and representative imports. Apply the same procedure to live data only after the restore rehearsal passes. Keep the original image and verified backup for recovery; do not point the older image at migrated data. See the [PostGIS 3.6 upgrade instructions](https://postgis.net/2025/09/PostGIS-3.6.0/).
