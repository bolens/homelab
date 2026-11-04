# Changedetection.io

Monitor website content, prices, and restocks and send change notifications to Gotify.

**Website:** https://changedetection.io/
**Docs:** https://github.com/dgtlmoon/changedetection.io/wiki
**GitHub:** https://github.com/dgtlmoon/changedetection.io

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

Caddy on `ingress-admin`, upstream `changedetection:5000`. No host port is published.

- `changedetection_data` at `/datastore`.

Images are pinned by version and digest in Compose. Configure timezone through `stack.env`. The generated catalog metadata is in `stack.yaml`.

## Browser and notifications

Basic HTTP watches run without another container. For JavaScript pages, enable the optional browser override after reviewing its memory use and browsing credentials. Set the browser fetch method in each applicable watch. No browser-control port is published or attached to ingress. In Settings, set a password before public access and configure a dedicated Gotify application using `gotify://gotify/APPLICATION_TOKEN`.

## Verification, upgrades, and recovery

Check container health, open the application through its intended route, and complete an authenticated application operation. A passing health probe does not prove onboarding, external provider access, notification delivery, or device playback.

Before upgrades, record the exact image and configuration and back up all declared persistent volumes and private environment files with writers quiesced or application-consistent methods. Restore copies in isolation and verify database integrity, file hashes, and representative records. Preserve credentials and encryption keys with their matching data. Do not assume an older image can read an upgraded database. If verification fails, stop the changed service and restore verified state with the original compatible image. Never use `docker compose down -v` during routine maintenance.
