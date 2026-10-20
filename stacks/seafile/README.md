# Seafile – file sync and sharing

[Seafile](https://www.seafile.com/) is a self-hosted file sync and sharing platform with desktop and mobile clients. This example runs Seafile 14 Community Edition with MariaDB and an authenticated Redis cache behind Caddy.

**Website:** https://www.seafile.com/  
**Docs:** https://manual.seafile.com/14.0/<br>
**Docker image:** https://hub.docker.com/r/seafileltd/seafile-mc  

## Fresh installation

Existing installations must complete [Upgrading from Seafile 13](#upgrading-from-seafile-13) first.

1. Run `./prepare-stack.sh` to copy the public examples. Preparation preserves an existing `stack.env` and Caddy snippet, mirrors `stack.env` into `.env` for Compose interpolation, and ensures `ingress-public` exists. It does not start containers or migrate settings.
2. Edit `stack.env`:
   - Set `MYSQL_ROOT_PASSWORD`, `SEAFILE_DB_PASSWORD`, `REDIS_PASSWORD` and `JWT_PRIVATE_KEY` to independent generated secrets. Use `openssl rand -hex 32` for the Redis password and JWT key.
   - Set `SEAFILE_SERVER_HOSTNAME` to your public hostname and `SEAFILE_SERVER_PROTOCOL=https` when Caddy terminates TLS.
   - Set `INIT_SEAFILE_ADMIN_EMAIL` and `INIT_SEAFILE_ADMIN_PASSWORD` for the initial administrator. They apply only on first initialization; an existing account is not reset. There is no first-visit administrator wizard to rely on.
3. Review `caddy_snippet.conf`, then rerun preparation to refresh `.env` after editing `stack.env`.
4. Deploy from this directory:

   ```bash
   docker compose --env-file stack.env up -d
   ```

5. Access Seafile through Caddy at your configured HTTPS hostname. The upstream container serves HTTP on port `80`; no host ports are published.

## Configuration

| Item | Contract |
| --- | --- |
| Access | Caddy → `seafile:80` over `ingress-public` |
| Private dependencies | MariaDB and Redis use only the default stack network, with no host ports |
| Images | `seafileltd/seafile-mc:14.0-latest`, `mariadb:13.0`, digest-pinned `redis:8-alpine` |
| Persistent state | `seafile_db12` → `/var/lib/mysql`; `seafile_data` → `/shared` (configuration, keys, libraries and logs) |
| Cache | Redis authentication required; snapshot/AOF persistence disabled; image `/data` volume masked by a disposable 16 MiB tmpfs |
| WebDAV | `ENABLE_SEAFDAV` and `SEAFDAV_WORKERS`; disabled by default |
| Metadata server | Optional separately deployed service; `ENABLE_METADATA_MANAGEMENT` and `INNER_METADATA_SERVER_URL` |
| Other extensions | SeaDoc, notification and AI services are disabled and not provisioned in this base example |
| Ingress example | [caddy_snippet.conf.example](caddy_snippet.conf.example) |

Redis runs as UID/GID `1000:1000`; its `/data` tmpfs is owned by that identity and has mode `0700`. It has no persistent cache volume. The Redis password is supplied to both Seafile and Redis from the same `stack.env` key. It is not published in a health-check response. Redis is a rebuildable cache; losing it can invalidate sessions or other cached state. Do not use it for another application's persistent data. Preserve the actual database names through the three `SEAFILE_MYSQL_DB_*_DB_NAME` variables; the defaults match the prior example. `SEAFILE_DB_NAME` is retained for the original MariaDB initialization contract and does not rename Seafile's three databases.

The `14.0-latest` application tag tracks maintenance releases. Record the exact resolved image before every deployment and review the selected release's notes. A portable example or passing Compose validation does not establish compatibility with an existing installation.

## Upgrading from Seafile 13

Use the official [13→14 Docker procedure](https://manual.seafile.com/14.0/upgrade/upgrade_docker_14.0/) and [14.0 upgrade notes](https://manual.seafile.com/14.0/upgrade/upgrade_notes/) alongside the steps below. This repository adapts upstream's bundle to existing named volumes and external Caddy; do not replace local Compose or environment files with the upstream download blindly.

### Record and verify recoverable state

1. Record all current image references/IDs, Compose and override files, private environment and ingress configuration, database names, cache choice and enabled extensions. Record users, libraries, file counts, representative file hashes and a working download/sync. Retain the current JWT key and other encryption/signing keys.
2. Quiesce Seafile and every optional extension or other writer that can change its databases or libraries. Keep the current cache state until old Seafile writers have stopped. Back up complete `seafile_db12`, `seafile_data`, private `stack.env`/`.env`, Compose/overrides, ingress settings and any separately stored extension state. Use an application-consistent database backup or a cleanly stopped database volume copy. Never copy an actively written MariaDB data directory as a backup.
3. Restore into isolated volumes/directories using the recorded previous images. Verify all backup files, database readability/integrity, the three configured databases and application counts/files. Keep the original volumes untouched. Test the 14.0 migration against a second isolated copy and verify login, libraries, original-file download and client sync before changing the live installation. Do not proceed if backup verification or the migration trial fails.

### Migrate the configuration explicitly

Preparation never edits `/shared` or inserts new keys into an existing `stack.env`. Apply the following changes deliberately after reviewing the private settings, retaining a copy of every original file:

- **Cache:** this example replaces Memcached with a new, non-persistent Redis service, following upstream's recommendation for Seafile 14 features. Add a generated `REDIS_PASSWORD` to the existing `stack.env`. Compose supplies `CACHE_PROVIDER=redis`, `REDIS_HOST=redis` and port `6379`. Remove obsolete Memcached overrides and confirm any persisted Seafile cache configuration agrees with these values. Do not migrate cache contents or remove an independently shared Memcached service. Stop old Seafile writers before switching; cached sessions may be lost and users may need to log in again.
- **WebDAV:** if previously enabled, carry its existing enablement and worker count into `ENABLE_SEAFDAV` and `SEAFDAV_WORKERS` in `stack.env`. Remove only the old `enabled` and `workers` options from `/shared/seafile/conf/seafdav.conf` (container path); preserve all other options. Test the existing WebDAV authentication and file access after migration.
- **Metadata:** if used, migrate `ENABLE_METADATA_MANAGEMENT` and `METADATA_SERVER_URL` from `seahub_settings.py` to `stack.env`, renaming the latter to `INNER_METADATA_SERVER_URL`. Use the reachable URL of the separately deployed server, upgrade that service with its own verified state and follow upstream's extension instructions. The example's placeholder hostname is not a provisioned service.
- **Local passwords/SSO:** remove obsolete `DISABLE_ADFS_USER_PWD_LOGIN`, `ENABLE_CHANGE_PASSWORD` and `ENABLE_SSO_USER_CHANGE_PASSWORD` settings if present. If external-provider users must be barred from local-password login/change/reset, explicitly preserve that policy using `DISABLE_SSO_USER_LOCAL_PWD_LOGIN=True` in `seahub_settings.py`. Do not accept the default until the prior policy has been compared. Verify existing local and external-provider authentication separately.
- **Traffic limits:** in every affected `ENABLED_ROLE_PERMISSIONS` entry, migrate `monthly_rate_limit` → `monthly_download_traffic_limit` and `monthly_rate_limit_per_user` → `monthly_download_traffic_limit_per_user`, preserving the exact existing values. The old keys are no longer read. Configure the independent upload allowances only if wanted; upstream uses `monthly_upload_traffic_limit` and `monthly_upload_traffic_limit_per_user`.
- **Extensions:** if SeaDoc, notification, thumbnails or AI are already in use, this base stack is insufficient. Preserve their settings and data and prepare reviewed overrides/services before deployment rather than accepting disabled features. Upgrade matching companion images. Follow upstream's thumbnail-setting rename, AI redeployment/obsolete-setting removal and face-recognition removal guidance. Do not remove their data automatically. Pro-edition search settings need the Pro upgrade procedure; this example is Community Edition.
- **Identity:** preserve the actual database names, credentials, hostname, protocol, JWT key, initial volume names and ingress choices. The initial-admin environment keys apply only to fresh installs; they do not replace an established account-management procedure.

### Apply, verify and roll back

After the isolated trial passes, apply only the reviewed configuration and application/cache changes. Keep MariaDB's image and existing volume identities unchanged during this Seafile migration. Rerun preparation to synchronize `.env`, then use the explicit Compose environment above to start the reviewed services. Do not use `down -v`, rename the volume keys or delete old data.

Confirm Seafile and Redis health, then compare every baseline: databases/users/libraries/file counts, representative file bytes, existing download and sync, configured authentication and any migrated WebDAV/metadata/extension behavior. Confirm TLS and generated public links through Caddy. Container health alone is insufficient. Remove an old **stack-owned** Memcached container only after successful acceptance and after verifying it is not shared.

If data is missing, migration fails or verification is inconclusive, stop the updated application and its writers. Restore the complete verified backup with the previous matching images, cache configuration, environment and overrides; a tag rollback cannot undo schema or configuration changes. Verify restored data and application behavior before resuming service. Retain the verified backup and record unresolved gaps; after success, remove only temporary backup/trial copies created for this operation, preserving existing retention policies.

## MariaDB upgrades are separate

The Compose database image remains `mariadb:13.0`. Existing MariaDB 12 installations must follow the [major upgrade and rollback procedure](../../documents/MARIADB-UPGRADES.md) before deployment. Do not combine an untested database-major migration with the Seafile 14 migration. Keep the existing volume keys, including the `12` suffix.

This source change has no live migration or data-preservation acceptance. The backup scope remains both persistent volumes plus configuration and any actual extension state.
