# Wallos

Track subscriptions, recurring expenses, and renewal notifications.

**Website:** https://wallosapp.com/
**Docs:** https://github.com/ellite/Wallos
**GitHub:** https://github.com/ellite/Wallos

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

Caddy on `ingress-sensitive`, upstream `wallos:80`. No host port is published.

- `wallos_db` at `/var/www/html/db`.
- `wallos_logos` at `/var/www/html/images/uploads/logos`.

Images are pinned by version and digest in Compose. Configure timezone through `stack.env`. The generated catalog metadata is in `stack.yaml`.

## Initial setup

Create the first account through private ingress before exposing the site. Add subscriptions and renewal dates. Configure a dedicated Gotify application in notification settings if desired. Both the database and uploaded logos are persistent. Exchange-rate integrations are optional and require their own provider credentials.

## Verification, upgrades, and recovery

Check container health, open the application through its intended route, and complete an authenticated application operation. A passing health probe does not prove onboarding, external provider access, notification delivery, or device playback.

Before upgrades, record the exact image and configuration and back up all declared persistent volumes and private environment files with writers quiesced or application-consistent methods. Restore copies in isolation and verify database integrity, file hashes, and representative records. Preserve credentials and encryption keys with their matching data. Do not assume an older image can read an upgraded database. If verification fails, stop the changed service and restore verified state with the original compatible image. Never use `docker compose down -v` during routine maintenance.
