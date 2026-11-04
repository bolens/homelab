# Zimi

Read, search and manage a Kiwix ZIM library through an authenticated web interface and API.

**Website / GitHub:** https://github.com/epheterson/Zimi
**Docs:** https://github.com/epheterson/Zimi/blob/v1.15.2/docs/features/operations.md
**Image:** https://hub.docker.com/r/epheterson/zimi

## Prepare and deploy

Run `./prepare-stack.sh`, set a unique `ZIMI_MANAGE_PASSWORD` in private `stack.env`, and review the Caddy aliases. Re-run preparation to synchronize `.env`. It preserves existing files and never starts containers. Deploy explicitly with `docker compose --env-file stack.env up -d`.

The v1.15.2 image is pinned by release tag and digest. The service runs as UID/GID 1000 with all capabilities dropped. Before its first start, run `docker compose --profile storage-init run --rm initialize-storage` to initialize only empty named-volume roots to UID/GID 1000. The one-shot helper has no network, only the CHOWN capability, and refuses nonempty roots with other ownership. It preserves already owned roots. Do not recursively change ownership of an existing library. Caddy proxies `zimi:8899` on `ingress-sensitive`. No host ports, host networking, devices or Docker socket are required. BitTorrent and Nearby discovery are disabled, so bridge networking does not promise mDNS or seeding. Do not publish port 6881 or multicast ports unless those features are deliberately adopted later.

## Access and library management

Library reads and management require authentication: `ZIMI_PUBLIC_ACCESS=private`, a named management user/password, `ZIMI_MANAGE_OPEN=0` and `ZIMI_LAN_ADMIN=0`. Supplying the password before first start avoids the remote first-admin claim window. Health remains reachable without an account. Keep API tokens and account state private. SSO is off unless separately configured with verified issuer/audience and proxy trust.

`zimi_library` at `/zims` is writable so operator-selected downloads can work. `zimi_config` at `/config` stores users, bookmarks, policy, indexes and settings. No existing ZIM collection is moved or scanned automatically. Bundled ZIM content shipped in the image may be available locally. Content auto-update, BitTorrent, discovery, application update checks, voice downloads and satellite updates are disabled. Catalog browsing and explicitly requested HTTP downloads remain available. Choose collections and storage capacity before downloading.

## Verification and persistence

Check `/health`, then verify private library/management endpoints refuse anonymous requests. Sign in through the native account flow and read the library and management status. Verify zero active downloads and disabled automatic/network-sharing work. Confirm settings survive a restart and the intended local Caddy route validates TLS. No sample Internet download is needed to prove deployment.

## Backup, updates and recovery

Before changing an existing install, record image/configuration, users, ZIM identities and active jobs. Stop writers and back up both complete volumes and private environment files. `zimi backup` can additionally export server state, but excludes the ZIM files themselves. Restore private copies in isolation, compare file hashes, check JSON/SQLite readability and native login/library state using the matching image. Do not copy an old binary over a migrated database. On failure restore verified prior state/configuration/image and verify library identities before resuming. Never use routine destructive volume removal. Clean up only this operation's temporary backup and restore copies after successful verification.
