# MariaDB major upgrades

These instructions cover the database services in Matomo, RomM, Seafile, Snipe-IT and YOURLS. New empty databases initialize with the selected image. Existing databases need a planned upgrade; changing a Compose tag does not prove compatibility or update the system tables. Read the target release notes and application database requirements first.

| Stack | Database service | Application service | Database volume key |
| --- | --- | --- | --- |
| Matomo | `matomo-db` | `matomo` | `matomo_db12` |
| RomM | `romm-db` | `romm` | `romm_mysql12_data` |
| Seafile | `db` | `seafile` | `seafile_db12` |
| Snipe-IT | `snipeit-db` | `snipeit` | `snipeit_db12` |
| YOURLS | `yourls-db` | `yourls` | `yourls_db12_data` |

The `12` in existing volume keys is a storage identity, not an instruction to rename them for MariaDB 13. Keep the same data sources. Resolve their effective Docker volume names and any operator bind overrides privately; a renamed or missing volume can initialize an empty database.

## Before starting the new database

1. Resolve and record the intended target image digest. Retain the prior database and application image IDs, Compose configuration, volume/bind sources, database names, table/record counts and application checks. Keep credentials and database output outside Git.
2. Stop the application and every other writer to this database, then stop the database cleanly. Back up the complete database directory, configuration and affected application state listed in the owning README. Use an application-consistent method or a stopped copy; a live file copy is not sufficient.
3. Restore that backup into separate storage and verify completeness, file integrity, database readability and application records using the prior images. The restore must not attach original volumes, writable binds or production networks. A different Compose project name alone does not isolate explicitly named volumes. Do not start the new database until this restore succeeds.

## Upgrade and verify

From the selected stack directory, use its database service from the table. For example, RomM uses `romm-db`:

```bash
docker compose --env-file stack.env up -d --no-deps --pull never romm-db
docker compose --env-file stack.env exec romm-db mariadb-upgrade --user=root --password
docker compose --env-file stack.env exec romm-db mariadb-check --user=root --password --all-databases --check-upgrade
```

Pull and verify the selected target image before these commands. Keep the application stopped during them. The clients prompt for the existing database root password; do not put it in shell history or shared output. Check all exit statuses and database logs, then compare schemas and table/record counts with the baseline. A passing container health check does not establish upgrade completion. These examples use an explicit operator-run system-table upgrade; they do not enable `MARIADB_AUTO_UPGRADE` or disable the image's upgrade backup.

Start the application only after database checks pass. Verify login and the owning README's application checks, preserved records and files, and any application migration before accepting the upgrade. A configured app image update may also migrate state and belongs in the same rollback scope.

## Rollback

If verification fails, stop the updated application and database. Restore the verified pre-upgrade database, configuration and affected application state into their recorded locations, select both prior images and verify recovery before resuming writes. Starting an older MariaDB image against an upgraded data directory is not a rollback. Keep unresolved originals and the verified backup until recovery or upgrade acceptance; remove only operation-owned temporary copies afterward under the existing retention policy.

See MariaDB's [major upgrade requirements](https://mariadb.com/docs/server/server-management/install-and-upgrade-mariadb/upgrading/platform-specific-upgrade-guides/upgrading-on-linux/upgrading-between-major-mariadb-versions), [system-table upgrade tool](https://mariadb.com/docs/server/clients-and-utilities/deployment-tools/mariadb-upgrade), [Docker upgrade option](https://mariadb.com/docs/server/server-management/automated-mariadb-deployment-and-administration/docker-and-mariadb/mariadb-server-docker-official-image-environment-variables) and [major downgrade restrictions](https://mariadb.com/docs/server/server-management/install-and-upgrade-mariadb/downgrading-between-major-versions-of-mariadb).
