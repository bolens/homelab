# Tasks: Immich per-user photo storage

## Setup

- [x] T001 Record acceptance criteria and rollback ordering in `specs/033-immich-user-storage/spec.md` and `plan.md`.

## Foundation

- [x] T002 Capture and verify a private live backup before changing `stacks/immich/` runtime storage.

## User story 1: Per-user originals

- [x] T003 [US1] Add `stacks/immich/docker-compose.storage.yml` and environment/preparation documentation.
- [x] T004 [US1] Validate missing-input safety and base preservation in `scripts/tests/test_immich_storage.py`.
- [x] T005 [US1] Deploy the selected bind mount and account label using ignored `stacks/immich/` inputs and Immich UI.
- [x] T006 [US1] Verify mount writes and future-user label/ID selection; record evidence here.

## User story 2: Preservation

- [x] T007 [US2] Compare live account/asset counts and existing files against the private backup; record evidence here.

## Final verification

- [x] T008 Run `make validate`, inspect the scoped diff and record results in this file.
- [x] T009 Remove operation-owned private backup/restore copies after successful preservation checks.

## Dependencies and execution

Execute T001 through T009 serially. Repository edits may be prepared while the
backup completes, but runtime changes depend on T002. T005 depends on T003 and
T004. T009 depends on T006 through T008. No delegated or parallel agent work.

## Acceptance evidence

Verified on 2026-10-31:

- Four focused tests passed: optional mount preserves the base model, missing
  variables refuse rendering, missing directories are not created, and repeated
  preparation preserves settings and refreshes Compose selection.
- `make validate` passed. The externally generated PostHog bundle was skipped;
  the existing Stoat optional-example preparation warning remains. YAML and
  Markdown checks also covered newly added, untracked feature files explicitly.
- All four persistent volumes were archived while stopped, restored in isolation,
  and compared byte for byte. Restored PostgreSQL opened, record counts matched,
  and `pg_amcheck --heapallindexed` passed.
- The running server has the NFS bind at `/data/library` and keeps its named
  volume at `/data`. A unique server-written probe matched its host-side SHA-256
  and was removed. The remote user directory remains ready for uploads.
- The installed image's actual template renderer produced the expected dated
  filename. Its path builder selected distinct labelled-user and future-user-ID
  folders. No production test account was created.
- The authenticated browser retained the saved template, account label and
  enabled hash verification after a reload. A screenshot was saved outside Git.
- All 20 baseline application files remain. Only startup `.immich` markers may
  change. Asset/account/album counts match. All account fields except the intended
  label and change markers match; global configuration differs only in the
  requested template. A complete post-change database dump succeeded.
- All four production containers are healthy and the server API responds.
- The library had zero assets, so no existing-asset migration job was needed.
  A real upload was not performed. Validation used the installed renderer,
  authenticated preview and a filesystem probe.

Operation-created backup/restore copies and the unique write probe were removed
after successful verification. The original named volumes were preserved.
