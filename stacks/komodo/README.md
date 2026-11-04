# Komodo

Controlled Docker and Compose management, with automatic updates disabled during initial onboarding.

**Website:** https://komo.do/
**Docs:** https://komo.do/docs/
**GitHub:** https://github.com/moghtech/komodo

## Prepare and deploy

Run `./prepare-stack.sh`, edit private `stack.env` and Caddy hostnames, and review the onboarding requirements below before starting. Preparation preserves existing files and never starts containers. Images are pinned by version and digest.

Caddy reaches `komodo-core:9120` through `ingress-admin`. There are no published host ports.

## Onboarding and runtime authority

Set unique database, administrator, JWT, and webhook secrets before first start. Core and Periphery share generated Noise keys at `/config/keys`; Periphery connects outbound to Core without a published agent port. The local administrator and Local server initialize automatically. Disable-init-resources prevents creation of the default global auto-update procedure. Registration, non-administrator resource creation, host terminals and container terminals are disabled. Confirmation dialogs remain enabled.

Periphery's Docker socket mount grants host-level control even with `:ro`. This is an explicit management capability. There is no host `/proc` mount, privileged mode, or host networking. The management root is a separate application-local directory bound at the identical absolute host/container path. Verify its parent filesystem before preparation, and include it in backups. Never point it at a missing remote mount or the shared working repository.

Initially observe the existing containers only. Keep Watchtower stopped and Portainer available. Do not create or deploy imported Stack resources or enable automatic updates. Future adoption must preserve the exact original Compose project name, file/override set, working directory, volumes and environment. Komodo deployment writes `.env`, so importing a stack is a separate reviewed migration, not an inventory action.

## Verification

Check `/version`, native administrator login, rejection of anonymous `/read` requests, disabled registration and absent procedures/stacks, Local server connectivity and Docker inventory. Compare existing container IDs and start times before/after onboarding. No existing stack is redeployed by this initial setup.

## Backup and rollback

Back up every declared persistent volume, private configuration, credentials and any application-local bind directory before upgrades. Quiesce writers or use consistent database dumps. Restore copies in isolation and verify database readability, file integrity, counts and representative application operations. Preserve original compatible images. On failure stop the changed application and restore verified original data/configuration and image. Never use destructive volume removal for routine maintenance. Remove only operation-created backup and test restore copies after acceptance.
