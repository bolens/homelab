# Implementation Plan: Immich per-user photo storage

**Date**: 2026-10-31 | **Spec**: [spec.md](spec.md)

## Summary

Add an explicit `docker-compose.storage.yml` override binding
`IMMICH_LIBRARY_PATH` to `/data/library`. Keep the existing named volume at
`/data` for staging, generated media, profiles and dumps. Immich's enabled
storage template chooses a storage label or account ID below the bound directory.

## Technical Context

- Platform: Linux, Docker Compose, Immich v3.3.5, PostgreSQL 16 and NFS.
- Sources: `stacks/immich/` and a dedicated isolated storage-contract test.
- Tests: Compose rendering, preparation fixtures, read-only repository gate,
  private restore drill, mount write/read, database counts and signed-in browser.
- Scope: Existing account plus future accounts. No production test users.
- Performance: Retain local generated files. Cross-filesystem finalization uses
  Immich's hash verification. Monitor remote capacity separately from `/data`.

## Constitution Check

All five principles pass before and after design. Examples use portable paths;
live settings remain ignored. Only affected contracts change. Preparation never
creates remote directories or starts containers. The optional writable mount is
explicit, refuses host path creation, and has documented backup requirements.

## Project Structure

- `stacks/immich/docker-compose.storage.yml`: optional original-file mount.
- `stacks/immich/stack.env.example`: commented portable path example.
- `stacks/immich/prepare-stack.sh`: opt-in path existence check and guidance.
- `stacks/immich/README.md`, `stack.yaml`: storage and backup ownership.
- `scripts/tests/test_immich_storage.py`: isolated safety regressions.
- `specs/033-immich-user-storage/`: requirements, design and acceptance record.

## Migration and rollback

1. Capture current images, configuration, account settings and record counts.
2. Stop writers/dependencies and archive all four persistent volumes privately.
3. Restore the archive to isolated storage, compare all bytes, open the restored
   database and run its integrity check. Resume the previous stack for UI changes.
4. Verify the real remote mount, create only its new Immich destination, and copy
   the existing `library/` subtree without overwriting any existing destination.
5. Set the current account's storage label in Immich. Use the global template
   `{{y}}/{{MM}}/{{dd}}/{{y}}{{MM}}{{dd}}_{{HH}}{{mm}}{{ss}}_{{filename}}` and retain
   hash verification. Configure the optional mount through ignored
   runtime Compose inputs and recreate only the server.
6. Verify records, baseline files, mount identity, write/read/delete of a unique
   probe, server health, authenticated UI and multi-user folder selection.
7. On failure, stop writers, restore the prior Compose configuration and the
   verified state as needed. Preserve the original named volume throughout.
8. After success, remove only operation-created backup and restore resources.

No image, port, network, ingress, database location or authentication change is planned.
