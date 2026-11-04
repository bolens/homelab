# TubeArchivist

Archive and browse a YouTube video library with subscriptions, playlists and searchable metadata.

**Website:** https://www.tubearchivist.com/
**Docs:** https://docs.tubearchivist.com/installation/docker-compose/
**GitHub:** https://github.com/tubearchivist/tubearchivist

## Prepare and deploy

Run `./prepare-stack.sh`, set unique `TA_PASSWORD` and `ELASTIC_PASSWORD` values in private `stack.env`, and list every exact browser origin in the space-separated `TA_HOST`. Re-run preparation to synchronize `.env`. Existing environment and Caddy files are preserved and preparation never starts containers.

The pinned v0.6.0 application uses dedicated Elasticsearch 9.5.5 and Redis 8 services. The bundled Elasticsearch image is amd64 only. Review the official Elasticsearch image for another architecture. The host needs `vm.max_map_count` of at least 262144, sufficient file descriptors and roughly 5 GiB for these explicit container limits. Preparation reports the prerequisite without changing host kernel settings.

Deploy explicitly with `docker compose --env-file stack.env up -d`. Caddy reaches `tubearchivist:8000` on `ingress-sensitive`; there are no published host ports. Elasticsearch and Redis use only the internal project backend and are not shared with other stacks. Local Caddy aliases are included, with opt-in placeholder public examples.

## Persistence and initial setup

Four named volumes keep `/youtube`, `/cache`, Redis `/data`, and Elasticsearch `/usr/share/elasticsearch/data`. `/cache` holds application state and artwork, not disposable cache. Initial deployment does not import or move MeTube files or start subscriptions/downloads. Choose media capacity, subscriptions, retention and download policy in the application before ingestion. The base uses Docker-managed storage. A future bind mount or library migration needs verified mount identity and a separate preservation plan, with `create_host_path: false`.

Sign in with the private initial account and verify `/api/user/me/`, the library and pending downloads. Confirm anonymous API reads fail and local HTTPS login works without CSRF/host errors. The health endpoint alone does not prove login or storage recovery. Optional notifications and upstream cookies belong in private application state, never in exported examples.

## Backup, updates and recovery

Before changing an existing deployment, record its exact images, credentials, configuration, library IDs/counts and mount locations. Quiesce the app and workers and back up all four volumes, including SQLite/auth state in `/cache`, plus private environment files. An application-consistent Elasticsearch snapshot is an alternative when properly configured. Keep media with matching metadata. Restore into isolated matching images, check SQLite integrity and Elasticsearch readability, compare representative library records/files and verify authentication before updating.

Keep the prior compatible images for rollback. If acceptance fails, stop the changed app and restore the verified configuration/state with those images. Never initialize over a missing disk, remove service volumes routinely or delete the existing MeTube library. Remove only operation-created temporary backup/restore copies after verified success or rollback.
