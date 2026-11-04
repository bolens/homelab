# Termix

Self-hosted SSH and remote desktop management with a browser terminal, file tools, and optional plugins.

**Website:** https://termix.site/
**Docs:** https://docs.termix.site/
**GitHub:** https://github.com/Termix-SSH/Termix

## Prepare and deploy

1. Run `./prepare-stack.sh`. It preserves existing files, ensures `ingress-admin`, copies the ingress example, and synchronizes `stack.env` to `.env`. It does not start containers.
2. Review private `stack.env` and `caddy_snippet.conf`. Keep the UI private while creating the first administrator and reviewing registration settings.
3. Validate and explicitly deploy:

   ```bash
   docker compose --env-file stack.env config --quiet
   docker compose --env-file stack.env up -d
   docker compose ps
   ```

4. Caddy routes to `termix:8080` on `ingress-admin`; there are no host ports. Caddy handles WebSocket upgrades for terminal sessions automatically.
5. Create the first administrator and add only the hosts and credentials you intend to manage. Test an authenticated terminal session against an authorized target. No host, SSH key, or Docker endpoint is added automatically.

## Access, secrets, and plugins

The version and digest are pinned in Compose. This standalone deployment uses the upstream standard plugin set and its single-instance defaults. The app creates its database and encryption/authentication material in `termix_data` at `/app/data`. That volume contains host inventory, SSH credentials and keys, plugin data, and secrets. Back up the complete volume, including generated keys.

Native application authentication remains enabled. Trusted proxy authentication is not enabled. Do not trust arbitrary forwarded identity headers. Keep remote-management access behind the same private or administrative ingress controls used for other host-management tools. Review optional plugins before enabling them. This stack grants no Docker socket access, host networking, privileged mode, or workstation SSH directory mounts. Remote capabilities depend on credentials and permissions explicitly configured in Termix.

The health probe uses the upstream backend endpoint on internal port 30001. Browser traffic uses the image's nginx listener on 8080. Changing PORT requires matching the Caddy upstream; it does not change the backend health port.

## Verify, upgrade, and recover

Check health, authenticated login, terminal WebSocket connectivity, and an authorized SSH session. Host reachability and SSH credentials must be configured separately; a healthy container does not prove them.

Before upgrading, record image identity and settings, quiesce the application and back up the entire data volume and private environment. Restore an isolated copy with the original compatible image, no production network access, and no host ports. Verify database readability, host records and matching encryption keys. After an upgrade compare record counts and test login and a representative connection. On failure restore the verified prior data and compatible image. Never delete the volume or assume image rollback alone can reverse a database migration. Remove only operation-created backup/restore copies after verification.

After creating the first administrator, disable new-user registration in the native administration settings and verify the administrator can still sign in. Adding SSH targets requires the intended host, username and authentication method. Do not import workstation private keys or Docker-managed host credentials automatically.
