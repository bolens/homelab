# Restic backups (cron)

Automated backups using [restic](https://restic.readthedocs.io/) running on a schedule, typically targeting an S3-compatible object store such as the `minio` stack in this repo.

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
   - `RESTIC_PATH_DOCKER` / `RESTIC_PATH_MEDIA` (host paths to back up; defaults `/srv/docker`, `/srv/media`),
   - and adjust `BACKUP_CRON` if needed.

2. **Initialize the repo (first run)**:

   ```bash
   docker compose --env-file stack.env up -d
   # Then inside the container (once per repository):
   docker compose exec restic restic init
   ```

3. **Run a manual backup (optional)**:

   ```bash
   docker compose exec restic restic backup /data/docker /data/media
   ```

4. **Let the scheduler run**
   - The container runs backups automatically according to `BACKUP_CRON`. Check logs with:

     ```bash
     docker compose logs -f restic
     ```

## Portainer

Stacks → Add stack → **Repository** → set your repo URL and Compose path (e.g. `stacks/restic/docker-compose.yml`). In **Environment**, set all required vars including `RESTIC_PATH_DOCKER` and `RESTIC_PATH_MEDIA` to absolute host paths (e.g. `/srv/docker`, `/srv/media`). Ensure MinIO is deployed and the `restic` bucket exists.

## Configuration

| Item        | Details                                                                 |
| ----------- | ----------------------------------------------------------------------- |
| **Type**    | CLI / cron-only stack (no web UI, no Caddy, no host ports)             |
| **Image**   | `mazzolino/restic:latest`                                              |
| **Network** | `monitor` (so it can reach `minio` or other S3 endpoints on that net)  |
| **Storage** | `restic_cache` (restic cache); data is stored in the remote repository |

## Key environment variables

Set these in `stack.env` (see `stack.env.example` for comments and examples):

- `RESTIC_REPOSITORY` – Repository URL, e.g. `s3:http://minio:9000/restic`.
- `RESTIC_PASSWORD` – Required encryption password. Generate with `openssl rand -base64 32`.
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` – S3 credentials for the backup target (e.g. MinIO).
- `RESTIC_PATH_DOCKER`, `RESTIC_PATH_MEDIA` – Host paths to back up (defaults `/srv/docker`, `/srv/media`). Set in Portainer to absolute paths.
- `BACKUP_CRON` – Cron schedule, default `0 3 * * *` (daily at 03:00).
- `TZ` – Optional timezone for logs and cron.

## Notes

- This stack assumes you have an S3-compatible backend (e.g. the `minio` stack) reachable on the `monitor` network. For shared MinIO setup and one-time checklist, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
- Restores are performed via the CLI inside the container, e.g.:

  ```bash
  docker compose exec restic restic restore latest --target /restore
  ```

  Adjust target and paths to match your use case.

