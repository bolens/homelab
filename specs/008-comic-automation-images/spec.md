# Feature Specification: Published comic automation images

**Created**: 2026-09-24

**Status**: Delivered; optional merged-branch cleanup awaits authorization

**Input**: Merge the comic automation changes into GitHub and publish the enhancements
in GHCR images so redeployment does not require local source code.

## User scenarios and acceptance

1. An operator deploys published Mylar and comic-normalizer images with existing
   application data and configuration; queue fixes, recovery, and navigation work
   without source-code bind mounts.
2. A pull request builds and tests both images without publishing. Its reviewed
   merge publishes commit-addressed images through the existing trusted-main workflow.
3. The operator can pin a published digest and roll back to a prior digest while
   retaining configuration, library files, and recovery receipts.

## Requirements

- Include all requested comic automation code and documentation, excluding secrets,
  runtime state, private diagnostics, and unrelated work.
- Use pinned upstream inputs, narrow build contexts, existing GHCR conventions,
  and the existing pull-request/merge protections.
- Preserve mounts, user identity, network access, resource limits, and health checks.
- Provide image override settings and document source-mount migration and rollback.
- Verify published artifact identity and live behavior with backed-up persistent state.

## Success criteria

The pull request is squash-merged with applicable checks passing. Both images are
available at the merged commit tag and verified digest. A redeployment uses those
images without source binds and passes health, representative behavior, and data
preservation checks. Temporary operation backups are removed only after success.

## Scope

OCI Linux/amd64 images are supported and exercised by the existing runner and target
host. ARM64 is conditional on separate runtime verification. Native package-manager,
desktop-store, Windows/macOS installer, and source/binary package variants are
inapplicable to this Compose-stack delivery. No product version or release tag is
introduced; main's commit tag and digest identify each publication.
