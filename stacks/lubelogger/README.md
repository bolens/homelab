# LubeLogger

Track vehicle maintenance, fuel use, receipts, and reminders.

**Website:** https://lubelogger.com/
**Docs:** https://docs.lubelogger.com/
**GitHub:** https://github.com/hargata/lubelog

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

Caddy on `ingress-sensitive`, upstream `lubelogger:8080`. No host port is published.

- `lubelogger_data` at `/App/data`.
- `lubelogger_keys` at `/root/.aspnet/DataProtection-Keys`.

Images are pinned by version and digest in Compose. Configure timezone through `stack.env`. The generated catalog metadata is in `stack.yaml`.

## Initial setup

Enable local authentication and create an administrator before adding public ingress. Keep both the data and ASP.NET Data Protection key volumes together during backup/restore. Add vehicles and maintenance schedules through the application.

## Verification, upgrades, and recovery

Check container health, open the application through its intended route, and complete an authenticated application operation. A passing health probe does not prove onboarding, external provider access, notification delivery, or device playback.

Before upgrades, record the exact image and configuration and back up all declared persistent volumes and private environment files with writers quiesced or application-consistent methods. Restore copies in isolation and verify database integrity, file hashes, and representative records. Preserve credentials and encryption keys with their matching data. Do not assume an older image can read an upgraded database. If verification fails, stop the changed service and restore verified state with the original compatible image. Never use `docker compose down -v` during routine maintenance.
