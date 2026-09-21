# Restic backups (cron)

Automated backups using [restic](https://restic.readthedocs.io/) running on a schedule, typically targeting an S3-compatible object store such as the `minio` stack in this repo.

The container uses the dedicated external `backup` network instead of the
shared application network. Attach the backup target, such as MinIO, to the
same network. A second internal `monitoring-push` network provides only the
dead-man callback path to Uptime Kuma.

**Website (restic):** https://restic.net  
**Docs (restic):** https://restic.readthedocs.io/  
**Image (mazzolino/restic):** https://github.com/djmaze/resticker

## Quick start

1. **Prepare** (copy template, set paths):

   ```bash
   ./prepare-stack.sh
   # or: cp stack.env.example stack.env
   ```

   Edit `stack.env` and set at least:
   - `RESTIC_REPOSITORY` (e.g. `s3:http://minio:9000/restic` when using the `minio` stack),
   - `RESTIC_PASSWORD` (encryption password; generate with `openssl rand -base64 32`),
   - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (S3 credentials),
   - `RESTIC_PATH_DOCKER`, `RESTIC_PATH_APPDATA`, and `RESTIC_PATH_MEDIA`
     (host paths to back up),
   - `UPTIME_KUMA_RESTIC_PUSH_TOKEN`, matching the Restic push monitor token,
   - and adjust `BACKUP_CRON` if needed.

2. **Initialize the repo (first run)**:

   ```bash
   docker compose --env-file stack.env up -d
   # Then inside the container (once per repository):
   docker compose exec restic restic init
   ```

3. **Run a manual backup (optional)**:

   ```bash
   docker compose exec restic restic backup /data/docker /data/appdata /data/media
   ```

4. **Let the scheduler run**
   - The container runs backups automatically according to `BACKUP_CRON`. Check logs with:

     ```bash
     docker compose logs -f restic
     ```

   Successful, incomplete, and failed backup runs update the `Restic Backup`
   push monitor in Uptime Kuma. The default daily schedule uses a 26-hour
   heartbeat grace period.

## Local backup disk

Use the optional override to write a new encrypted repository to a local backup
disk. Existing S3 backups remain untouched. The override retains the encryption
password from `stack.env` and does not migrate or delete old snapshots.

First verify the destination's mount identity, free space, and write access with
`findmnt -T /srv/backups` and `df -h /srv/backups`. Create the repository directory
only after verifying the intended backup disk is mounted. Compose refuses to
create a missing bind directory.

```bash
RESTIC_LOCAL_PATH=/srv/backups/restic docker compose --env-file stack.env \
  -f docker-compose.yml -f docker-compose.local-backup.yml up -d --pull never
```

Use this same override and host path for subsequent deployments. Starting the
base Compose file alone selects the original repository again.

Local mode backs up `/data/docker` and `/data/appdata` daily at 03:00 using the
image's six-field cron syntax. It excludes the MinIO Restic repository and Restic
cache listed in `local-excludes.txt`. The exclusion file also omits Kasm's inner
Docker `overlay2` layers, while retaining its named volumes, installation files,
and profiles. Kasm recovery requires recreating containers and obtaining their
images again. Changes stored only in excluded writable layers are not backed up.
Review these exclusions and volume names for your host.
Media is not selected, and backup-on-startup is disabled so the first run can be
checked deliberately. After a complete backup, local mode keeps 7 daily, 4 weekly,
and 3 monthly snapshots, plus at least the last 3 snapshots per source-path set.
Overlapping recovery points count once. Container hostname changes do not create
new retention groups. Failed or incomplete backups do not delete snapshots.
Local mode clears `RESTIC_REPOSITORY_FILE` and forces
`SUCCESS_ON_INCOMPLETE_BACKUP=false`, overriding inherited environment settings.

Unused backup data is pruned at most weekly, after a complete backup, with at
most 1 GiB of pack data selected for repacking per run. Retention failures report
a failed heartbeat to Uptime Kuma. `LOCAL_KEEP_LAST`, `LOCAL_KEEP_DAILY`,
`LOCAL_KEEP_WEEKLY`, and `LOCAL_KEEP_MONTHLY` override the positive retention
counts. These settings apply only to the new local repository. The old S3
repository is preserved.

Retention counts do not impose a byte limit. Reserve at least 15% of the backup
disk for growth and maintenance, and compare free space with the largest recent
backup's added data. The post-backup maintenance hook reports a failed heartbeat
when less than 20% is free, after attempting retention and any scheduled prune.
Review exclusions and capacity at that point, before the reserve is exhausted.
Keep application data and database dumps in scope.
Do not apply object-store expiration rules to Restic pack files.

```bash
docker exec restic backup
docker exec restic restic snapshots
docker exec restic restic check
```

Verify a restore into a new temporary directory before relying on the new
repository. Keep the repository password separately backed up. Restoring the
original Compose deployment returns the scheduler to S3, provided that backend
is available. Neither direction removes either repository.

## Portainer deployment

Stacks → Add stack → **Repository** → set your repo URL and Compose path (e.g. `stacks/restic/docker-compose.yml`). In **Environment**, set all required vars including `RESTIC_PATH_DOCKER` and `RESTIC_PATH_MEDIA` to absolute host paths (e.g. `/srv/docker`, `/srv/media`). Ensure MinIO is deployed and the `restic` bucket exists.

## Configuration

| Item        | Details                                                                 |
| ----------- | ----------------------------------------------------------------------- |
| **Type**    | CLI / cron-only stack (no web UI, no Caddy, no host ports)             |
| **Image**   | `mazzolino/restic:latest`                                              |
| **Network** | Isolated `backup` network plus internal `monitoring-push` callbacks   |
| **Storage** | Read-only backup sources at `/data/{docker,appdata,media}`; persistent cache at `/cache`; backup data in the remote repository |

## Key environment variables

Set these in `stack.env` (see `stack.env.example` for comments and examples):

- `RESTIC_REPOSITORY` – Repository URL, e.g. `s3:http://minio:9000/restic`.
- `RESTIC_PASSWORD` – Required encryption password. Generate with `openssl rand -base64 32`.
- `RESTIC_CACHE_DIR` – Fixed at `/cache`, backed by the `restic_cache` volume.
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` – S3 credentials for the backup target (e.g. MinIO).
- `RESTIC_PATH_DOCKER` – Repository and Compose files; defaults to `/srv/docker`.
- `RESTIC_PATH_APPDATA` – Docker named-volume data; defaults to
  `/srv/docker-volumes`.
- `RESTIC_PATH_MEDIA` – Shared media tree; defaults to `/srv/media`.
- `BACKUP_CRON` – Cron schedule, default `0 3 * * *` (daily at 03:00).
- `UPTIME_KUMA_RESTIC_PUSH_TOKEN` – Dead-man token shared with Uptime Kuma.
- `TZ` – Optional timezone for logs and cron.

## Notes

- This stack assumes you have an S3-compatible backend (e.g. the `minio` stack) reachable on the `backup` network. For shared MinIO setup and one-time checklist, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
- Restores are performed via the CLI inside the container, e.g.:

  ```bash
  docker compose exec restic restic restore latest --target /restore
  ```

  Adjust target and paths to match your use case.
- Raw application-data backups are crash-consistent. Use each database stack's
  dump procedure when a transaction-consistent database backup is required.
