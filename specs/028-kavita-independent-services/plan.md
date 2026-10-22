# Implementation Plan: Independent Kavita provider services

**Branch**: `codex/kavita-independent-services` | **Date**: 2026-10-22 | **Spec**: [spec.md](spec.md)

## Summary

Provide an opt-in LinuxServer-compatible Kavita fork and private provider gateway. The fork distinguishes independent feature availability from the official paid subscription. The gateway uses provider APIs directly and never calls the hosted Kavita+ backend. Target full functional parity, with explicit unsupported-capability errors until each provider/action is proven.

## Technical Context

**Language/Version**: Python 3.13 standard library gateway; upstream C# .NET 10 and Angular 22/Node 24.
**Primary Dependencies**: Upstream source commit `879b8b73eb41d66f88dde8eb874cc99a3397eb11`, installed LinuxServer base digest, provider HTTPS APIs.
**Storage**: Private SQLite cache and confirmed-operation receipts in a new sidecar volume; Kavita state stays in its existing volume.
**Testing**: Python unittest with transport fixtures, pinned-source patch checks, image compilation, isolated HTTP checks, genuine provider reads and separately admitted external writes.
**Target Platform**: Linux amd64 initially, preserve LinuxServer PUID/PGID and config layout.
**Project Type**: Optional Compose override, two custom container images.
**Performance Goals**: Bounded calls, provider-specific rate limits, cache public metadata, never cache private credentials in public metadata.
**Constraints**: No host/public gateway port, no Docker socket, no media writes, no fake subscription or unverified success.
**Scale/Scope**: One Kavita instance; Hardcover/MangaBaka metadata and AniList/MAL/Hardcover/MangaBaka sync capability matrix; ComicBookRoundup API coverage is a research/acceptance gap.

## Constitution Check

- Portable examples: placeholder credentials and operator-selected override.
- Complete contracts: Compose override, env example, preparation guidance, metadata and README updated together; ingress remains Kavita-only.
- Operations: isolated validation first; application-consistent verified backup before changing live Kavita.
- Security: authenticated internal backend, fixed provider origins, bounded bodies/responses, explicit credentials and no secret diagnostics.
- Validation: focused checks then `make validate`; source, image, provider and live evidence recorded separately.

All gates pass for isolated implementation. Each live image change remains gated on image proof and verified backup.

## Project Structure

```text
stacks/kavita/
  docker-compose.providers.yml
  providers/
    gateway.py
    metadata.py
    sync.py
    transport.py
    test_gateway.py
    test_metadata.py
    test_sync.py
    Dockerfile
  independent/
    Dockerfile
    patch_source.py
specs/028-kavita-independent-services/
  spec.md
  plan.md
  research.md
  data-model.md
  contracts/gateway.md
  quickstart.md
  tasks.md
```

## Ownership and execution

Root owns gateway, transport, Compose/docs and acceptance. Independent parallel tasks own metadata adapter/tests, sync adapter/tests, and fork patch/build files. These files share only the explicit adapter contract. No writer stages or commits another writer's changes.

## Account-test hardening follow-up

Implement FR-014–018 in provider adapters/transport and the pinned native patch. Use explicit sync-adapter capabilities rather than aggregated public metadata features. Keep official-mode behavior unchanged and isolate all failure/recovery tests from live accounts. Rebuild both images after focused fixtures and native compilation. Back up and restore both application and gateway state before live recreation, compare library/user/reading state, then remove only this operation's copies. Finish with a self-review and record remaining account acceptance gaps.


The gateway owns protected-entry deletion and post-delete confirmation in `providers/sync.py`. `providers/transport.py` stores host cooldown deadlines in SQLite and excludes GraphQL errors from cache. Cooldowns are bounded to one hour and never shortened by a later response.

The application owns a pure selected-provider/action policy shared by native admission and delivery, with a matching frontend policy. Only `adapters.sync` capabilities authorize personal writes. Creation can retain an action learned from the last valid manifest during transport outages. Delivery requires a fresh manifest. A valid manifest that removes an action disables new admission. Rereads and resets remain held.

Native JSON uses the web camelCase serializer on the independent client. The independent queue acknowledges only an explicit successful response without an error. Connection failures, expired credentials, rate limits, empty responses and unsupported operations remain pending. Official-mode behavior keeps its existing path.

The isolated native test uses the actual service, actual HTTP client, gateway process and persistent SQLite fixtures. A real upstream write is never needed for this gate. C# and TypeScript policies run the same case matrix. A self-review traces UI, admission, serialization, transport, confirmation and acknowledgment before image acceptance.

Rollout backs up both Kavita configuration and gateway state while stopped. Verify exact isolated restores and SQLite readability, then start candidate images against restored copies without external networking. Compare all metadata lock columns by primary key, library identities, user credentials/settings, roles and reading state. Apply the images to the existing networks and mounts only after proof. Preserve prior images for rollback and remove operation-created copies only after update or recovery verification.

## Recovery and storage follow-up

Disable inherited missing-token cleanup only in independent mode. Persist a bounded HMAC-authenticated creation snapshot under Kavita configuration, bound to origin and key. Use it for creation only, never delivery. Add bounded metadata cache and conservative receipt classes: old receipts and dated progress remain protected, while reconciled operations have bounded retention. Reserve protected capacity transactionally before writes, retain ambiguous reservations and refuse safely at capacity. Keep exact-ID maps stable and enforce a SQLite page budget without deleting persistent identities. Verify the actual native queue, source patch, gateway fixtures and both restored images before a backed-up live rollout.
