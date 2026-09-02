# Restic backups (cron)

Automated backups using [restic](https://restic.readthedocs.io/) running on a schedule, typically targeting an S3-compatible object store such as the `minio` stack in this repo.

The container uses the dedicated external `backup` network instead of the
shared application network. Attach the backup target, such as MinIO, to the
same network. A second internal `monitoring-push` network provides only the
dead-man callback path to Uptime Kuma.

**Website (restic):** https://restic.net  
**Docs (restic):** https://restic.readthedocs.io/  
**Image (mazzolino/restic):** https://github.com/mazzolino/docker-restic  

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

## Portainer

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
