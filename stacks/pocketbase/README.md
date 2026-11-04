# PocketBase

PocketBase provides a SQLite database, authentication, REST/realtime APIs, and an admin dashboard for small apps and homelab projects.

**Website:** https://pocketbase.io
**Docs:** https://pocketbase.io/docs
**GitHub:** https://github.com/pocketbase/pocketbase
**Docker image:** https://github.com/coollabsio/pocketbase

## Setup

1. Copy `stack.env.example` to `stack.env` and adjust optional settings.
2. Run `./prepare-stack.sh` to prepare missing environment and Caddy snippet files and the external `ingress-public` network.
3. Add the prepared Caddy snippet to your Caddy configuration and reload Caddy.
4. Deploy with `docker compose up -d`.
5. Open `https://pocketbase.home/_/` using your configured DNS and trusted Caddy CA, or your configured hostname.

No host port is published. Caddy must share `ingress-public` with PocketBase.
The public hostname blocks are examples. Configure public DNS, TLS, and any access policy separately before using them.

To create your first administrator account, use the image's CLI:

```sh
docker compose exec pocketbase sh -c '
  read -r -p "Email: " email
  read -r -s -p "Password: " password
  printf "\n"
  exec /app/pocketbase superuser create "$email" "$password"
'
```

Follow the interactive prompts. Keep credentials out of shell history and committed files.
Existing installations retain their superuser accounts.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| GOMEMLIMIT | No | (unset) | Go runtime memory limit, e.g. `256MiB` for constrained hosts |

TZ and locale come from the optional `shared.env`. The digest pins the image used by this stack.
PocketBase has no official Docker image. This stack uses `coollabsio/pocketbase`.

## Verify

Check `docker compose ps` for a healthy service, then request `/api/health` and `/_/` through your configured HTTPS hostname.
The health endpoint should return HTTP 200 and `API is healthy.`. The admin dashboard should load and accept your existing credentials.
The root `/` can return 404 when no custom frontend is installed.

## Persistence and recovery

The named volume `pocketbase-data` mounts at `/app/pb_data`, where this image stores its database, settings, and uploads.
Back up the entire data directory while PocketBase is stopped, or use its built-in backup facility.
Verify a restored copy, including SQLite integrity and file completeness, before an upgrade or repair.
Keep backups private and outside Git. See the [upstream backup guidance](https://pocketbase.io/docs/going-to-production/#backup-and-restore).

Older revisions mounted the volume at `/pb/pb_data`, which does not protect this image's default database directory.
Before recreating such a container, stop it and copy `/app/pb_data` from the existing container into a private backup.
Verify that backup and restore its contents to the named volume before applying the corrected mount.
Do not recreate first or overwrite an existing nonempty volume. Record the existing image digest and configuration for rollback.

After recreation, verify database integrity, application record counts, and uploaded files against the backup.
Confirm that another restart preserves the data and that the API and dashboard still work.
If verification fails, stop the repaired service and restore the verified data with the prior image and configuration before resuming use.
