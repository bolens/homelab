# Restic backups (cron)

Automated backups using [restic](https://restic.readthedocs.io/) running on a schedule, typically targeting an S3-compatible object store such as the `minio` stack in this repo.

**Website (restic):** https://restic.net  
**Docs (restic):** https://restic.readthedocs.io/  
**Image (mazzolino/restic):** https://github.com/mazzolino/docker-restic  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set at least:
     - `RESTIC_REPOSITORY` (e.g. `s3:http://minio:9000/restic` when using the `minio` stack),
     - `RESTIC_PASSWORD` (encryption password),
     - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (S3 credentials),
     - and adjust `BACKUP_CRON` if needed.
2. **Adjust source paths**
   - Edit `docker-compose.yml` and update the bind mounts under `volumes` to point at the host paths you want to back up (e.g. `/srv/docker`, `/srv/media`).
3. **Initialize the repo (first run)**
   - From this directory:

     ```bash
     docker compose up -d
     # Then inside the container (once per repository):
     docker compose exec restic restic init
     ```

4. **Run a manual backup (optional)**

   ```bash
   docker compose exec restic restic backup /data/docker /data/media
   ```

5. **Let the scheduler run**
   - The container runs backups automatically according to `BACKUP_CRON`. Check logs with:

     ```bash
     docker compose logs -f restic
     ```

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
- `BACKUP_CRON` – Cron schedule, default `0 3 * * *` (daily at 03:00).
- `TZ` – Optional timezone for logs and cron.

## Notes

- This stack assumes you have an S3-compatible backend (e.g. the `minio` stack) reachable on the `monitor` network. For shared MinIO setup and one-time checklist, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
- Restores are performed via the CLI inside the container, e.g.:

  ```bash
  docker compose exec restic restic restore latest --target /restore
  ```

  Adjust target and paths to match your use case.

