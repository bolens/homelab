# Backrest

Authenticated Restic snapshot browser and restore UI, with the existing repository mounted read-only and no competing scheduler.

**Website:** https://garethgeorge.github.io/backrest/
**Docs:** https://garethgeorge.github.io/backrest/
**GitHub:** https://github.com/garethgeorge/backrest

## Prepare and deploy

Run `./prepare-stack.sh`, edit private `stack.env` and Caddy hostnames, and review the onboarding requirements below before starting. Preparation preserves existing files and never starts containers. Images are pinned by version and digest.

Caddy reaches `backrest:9898` through `ingress-sensitive`. There are no published host ports.

## Seed authentication before startup

The upstream fresh default disables authentication. Keep ingress inactive until a private `config.json` is seeded. Copy `config.json.example` to ignored `config.json`, replace passwordBcrypt with **base64 of bcrypt hash bytes**, and leave `auth.disabled=false`. Do not put a plaintext password or a raw `$2b$` bcrypt string in that field.

Create without starting, then copy the private configuration:

```bash
docker compose --env-file stack.env create
docker cp config.json backrest:/config/config.json
docker compose --env-file stack.env up -d
```

The entire `/config` volume is writable because startup persists the generated instance identity. Only the repository itself is read-only. `/restore` is a separate volume, and no production source directories are mounted.

## Existing repository browser

Use `docker-compose.repository.yml` only after verifying the existing repository's mount identity and permissions. Keep `plans: []` and every repository's `hooks: []`. Obtain its existing GUID with authenticated `restic cat config`; do not guess it or initialize a new repository. Seed the repository privately with `uri=/repos/current`, its verified GUID and password, `flags=["--no-lock"]`, `autoUnlock=false`, `autoInitialize=false`, and all prune/check/forget policy schedules disabled. Do not use AddRepo to discover its GUID: that API can attempt initialization after a failed existence check.

Deploy with both Compose files. Import/indexing and browsing may update Backrest's own state, but the read-only mount prevents repository mutation. Check authentication before browsing existing backups. Compare snapshot IDs before and after import. Test a bounded restore into a fresh operation-owned `/restore` subdirectory and compare its hash to `restic dump` of the same file. Remove only that test restore after verification.

The existing Restic scheduler remains the sole backup/retention owner. Preserve its successful-backup gating, path-based retention, bounded weekly pruning, disk reserve, exclusions and Kuma callbacks. Both this release and the existing stack use Restic 0.19.1; BACKREST_RESTIC_COMMAND fixes the bundled engine instead of downloading another version.

## Command hooks

Do not configure command hooks in v1.14.1. [Upstream issue 1407](https://github.com/garethgeorge/backrest/issues/1407) reports shell injection through rendered command-hook input. This browser setup has no hooks or plans and cannot write to the repository. Review a fixed release before reconsidering scheduler ownership or command hooks. Native notification actions do not require shell hooks.

## Verification

Anonymous `/v1.Backrest/GetConfig` must return 401. Authenticate through the native login, compare snapshot IDs, browse a known path and complete a small isolated restore with matching contents. A 200 on the SPA alone does not prove repository access or recovery.

## Backup and rollback

Back up every declared persistent volume, private configuration, credentials and any application-local bind directory before upgrades. Quiesce writers or use consistent database dumps. Restore copies in isolation and verify database readability, file integrity, counts and representative application operations. Preserve original compatible images. On failure stop the changed application and restore verified original data/configuration and image. Never use destructive volume removal for routine maintenance. Remove only operation-created backup and test restore copies after acceptance.

Imported snapshots without Backrest plan tags appear under the native `_unassociated_` group. A direct restore API request must use that `planId` alongside `repoId`, `snapshotId`, `path` and a fresh target directory. This identifies the operation group and does not create a backup plan. Select a snapshot that actually contains the requested source path when comparing restore contents.
