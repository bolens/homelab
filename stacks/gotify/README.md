# Gotify

Authenticated push notifications with separate applications for monitoring, image updates, and workflow approvals.

**Website:** https://gotify.net/
**Docs:** https://gotify.net/docs/
**GitHub:** https://github.com/gotify/server

## Prepare and deploy

1. Run `./prepare-stack.sh`. It preserves existing files, ensures external networks, synchronizes `stack.env` to `.env`, and never starts containers.
2. Edit the private `stack.env`. Set a unique admin password before deployment. Create one application per producer and five Alertmanager categories. Put the application tokens in the corresponding private producer configuration and GOTIFY_TOKEN_* variables. Use a separate random GOTIFY_BRIDGE_TOKEN for Alertmanager authorization.
3. Review `caddy_snippet.conf`, replace placeholder hostnames, and import it into Caddy only after authentication is ready.
4. Validate and deploy explicitly:

   ```bash
   docker compose --env-file stack.env config --quiet
   docker compose --env-file stack.env up -d
   docker compose ps
   ```

## Access and persistence

Caddy on `ingress-admin`, upstream `gotify:80`. No host port is published.

- `gotify_data` at `/app/data`.

Images are pinned by version and digest in Compose. Configure timezone through `stack.env`. The generated catalog metadata is in `stack.yaml`.

## Notification migration

Gotify replaces ntfy. Its application tokens and message API are different. Old ntfy users, subscriptions, cache, and tokens are not imported. Keep the original ntfy volumes for historical access and rollback.

- Uptime Kuma: change the existing notification to type `gotify`, set `gotifyserverurl=http://gotify:80`, `gotifyapplicationToken` to its dedicated application token, and `gotifyPriority=5`. Keep its row ID and monitor bindings. Keep the existing SMTP fallback. Kuma must share `telemetry`.
- Diun: set `DIUN_NOTIF_GOTIFY_ENDPOINT=http://gotify:80` and `DIUN_NOTIF_GOTIFY_TOKEN` to its token. Remove only the old ntfy notifier variables.
- Watchtower: use `gotify://gotify:80/APPLICATION_TOKEN?disabletls=yes`. Keep a stopped Watchtower stopped.
- n8n: use the migrated restart approval template with an HTTP Header Auth credential named `Gotify Application`, header `X-Gotify-Key`. Approval and dismissal are Markdown links to the expiring Wait URL. No workflow is automatically activated.
- Changedetection.io: configure the Apprise notification URL `gotify://gotify/APPLICATION_TOKEN`. Use `gotifys://notify.example.com/APPLICATION_TOKEN` for a TLS route. Keep tokens out of exported watches.

### Alertmanager adapter

The companion accepts `POST /alertmanager/{channel}` on port 8080, where channel is `alerts`, `alerts-infra`, `alerts-blackbox-critical`, `alerts-blackbox-warning`, or `alerts-alloy`. Require `Authorization: Bearer <GOTIFY_BRIDGE_TOKEN>`. It converts firing/resolved groups into readable Gotify messages with severity priorities and annotation text. It publishes using a separate application token per channel. There are no host ports or Caddy routes for this adapter. Configure Alertmanager's `authorization.credentials_file` using its private `secrets/gotify-webhook-token` file. Invalid credentials, malformed requests, unknown channels, and failed Gotify delivery are errors, allowing Alertmanager to retry.

### Before cutover

Record producer configuration, images, message/monitor/workflow counts and persistent mounts. Quiesce affected writers, back up the complete state and private config outside Git, restore copies in isolation, and verify hashes and database integrity. Test each active producer and the HTTPS/WebSocket route before stopping ntfy. Preserve monitor history, workflow activation state, fallback routes and original ntfy data. On failure, restore verified prior config/state with compatible original images and restart ntfy. Remove only operation-created backup/restore copies after successful acceptance.

### Clients and access

Use the Gotify web UI or a compatible Gotify client with your server URL. Existing ntfy phone subscriptions do not transfer. Native Gotify API authentication protects producers and WebSocket clients. A browser-only SSO challenge over `/message` or `/stream` prevents native clients from connecting. Preserve Gotify token authentication on those routes. Caddy proxies WebSockets automatically.

## Verification, upgrades, and recovery

Check container health, open the application through its intended route, and complete an authenticated application operation. A passing health probe does not prove onboarding, external provider access, notification delivery, or device playback.

Before upgrades, record the exact image and configuration and back up all declared persistent volumes and private environment files with writers quiesced or application-consistent methods. Restore copies in isolation and verify database integrity, file hashes, and representative records. Preserve credentials and encryption keys with their matching data. Do not assume an older image can read an upgraded database. If verification fails, stop the changed service and restore verified state with the original compatible image. Never use `docker compose down -v` during routine maintenance.

## Optional Authentik notification plugin

The reviewed [Authentik plugin](https://github.com/ckocyigit/gotify-authentik-plugin) formats identity events as readable notifications. `plugins.lock.json` pins its v3.1.1 source commit, amd64 release binary checksum, Gotify version, and Go compiler. The plugin was validated against Gotify 3.1.1 with Go 1.26.0 and matching shared module versions. Recheck loader compatibility whenever the server or plugin version changes.

Run `./install-authentik-plugin.sh` explicitly to stage the verified binary, then deploy with `docker compose --env-file stack.env -f docker-compose.yml -f docker-compose.plugins.yml up -d`. The binary directory is ignored by Git and mounted read-only. Preparation does not download or enable plugins. Back up and verify the current Gotify data before enabling a plugin.

Enable the plugin for the intended administrator in Gotify. Configure an Authentik generic webhook transport using that user's private plugin webhook URL. Keep webhook mappings empty unless an explicitly reviewed mapping is required. Create a dedicated failed-login event policy and rule for the existing administrator group, with send-once delivery. Preserve other rules and transports. Do not enable generic event dumping or notify on every successful login by default. The plugin URL is a credential and belongs only in private Authentik configuration.
