# Tasks: Verified comic release naming

## Phase 1: Setup

- [x] T001 Record user naming preferences and preservation criteria in `spec.md`.
- [x] T002 Inspect pinned reader move/hash/progress contracts and document `research.md`.
- [x] T003 Define prospective data, API and rollback contracts in `plan.md`, `data-model.md`, `contracts/naming.md` and `quickstart.md`.

## Phase 2: Ownership and recovery foundations

- [x] T004 Add guarded native ownership/proposal resolution in `stacks/mylar3/config/release_naming.py`.
- [x] T005 Add no-overwrite native rename/catalog journal and recovery fencing in `release_naming.py`, `native_writers.py` and both copies of `media_writer.py`.
- [x] T006 Add primary-key versioned naming endpoints and image installation in `patch_release_naming.py`, `apply_patches.py` and `verify_image.py`.
- [x] T007 Verify stale ownership, metadata contradictions, collisions, partial publication and catalog failure with native tests.

## Phase 3: US1 — Normalizer release names

- [x] T008 Implement one renderer, label preservation and disabled-by-default policy in `stacks/komga/normalizer/release_naming.py`.
- [x] T009 Add XXH3 source/reader hash checks, restore-verified temporary copies, bounded serial follow-up and asynchronous reader proof.
- [x] T010 Integrate naming after conversion/tagging with `normalize.py`, `writer_cycle.py` and the worker image.
- [x] T011 Test annual, collected, fractional, variant, Unicode, source/group and publication-year cases plus native parser compatibility.

## Phase 4: US2 — Interrupted migration

- [x] T012 Test native/worker crash boundaries, uncertain acknowledgement reconciliation, writer contention and progress preservation.
- [x] T013 Update disabled-policy examples, preparation validation, module inventories, stack metadata and owning READMEs; regenerate affected catalog output.

## Phase 5: US3 — Bulk naming

- [x] T014 Add read-only manifests, source/catalog freshness checks, bounded apply/resume and idempotent second-pass tests.
- [x] T015 Complete focused/image/repository checks and independent review, then deliver the reviewed change through GitHub and the authorized mirror.
- [x] T016 Deploy compatible images with verified backups, enable the naming policy and prove one live rename.
- [ ] T017 Apply eligible bulk entries under coordination; verify exact contents, native ownership and reader readiness, recording every review/skip. Additional reading-progress audit is deferred by the user. Rebind existing repaired-file credit deferrals through verified old-to-new receipts before the supplement pass resumes.
- [ ] T018 Remove only conclusively completed temporary preservation copies and publish final acceptance evidence.
- [ ] T019 Close the live-discovered unbracketed edition-label gap and collection/regular-issue mismatch, with regression proof and reviewed delivery before bulk apply.

## Dependencies and execution

T004–T007 establish native ownership and recovery before live naming. T008–T011 share one renderer for new and existing normalized files. T012–T014 precede delivery; T016 precedes the bulk pass. Source work remains coordinated in one branch. Independent final review is required for the substantive PR; no parallel implementation is needed.

## Current evidence

- Bulk preflight found the 160-page Action Comics #1000 Deluxe Edition falsely owned by the regular issue. Actual title-page evidence and the publisher's separate hardcover listing establish the distinction. Corrective guards hold unbracketed edition/variant annotations and reject collected-edition suffixes against an ordinary issue, even with stale matching ComicInfo IDs. Live repair, independent review and delivery remain pending; bulk apply has not started.

- Renderer/policy suite: six tests pass, preserving dotted names, group suffixes, editions, source/language blocks, fractions, variants and conflicting-ID/year review.
- Native naming/API suite: sixteen tests pass, covering ownership and volume/group helpers, primary-key admission, collisions, stale requests, link/catalog interruption, journal binding, fenced admission and unchanged-byte/inode publication.
- Actual native parser suite: ten tests pass, including GN/TPB/HC with distinct run and issue volumes. Read-only actual-image source/final-name fixtures prove identical ownership and idempotence for Heavy Metal #197701, HalloweeNight collected volume 5, Grendel: Sedition #2 and the parent-owned Grimm 2020 Annual.
- Worker naming suite: twelve tests pass for verified preparation, interrupted-copy retry, uncertain acknowledgement reconciliation, hash uniqueness, progress gates, stale manifests, batch admission, partial-failure scan dispatch and idempotence. Existing writer-cycle tests plus the new native-fence regression pass.
- Read-only candidate checks reproduce the actual XXH3 hashes of three Komga books.
- Repository validation passed. The current worker candidate passes all 177 image tests without skips. The current Mylar candidate passes its complete native gates, including sixteen naming/API tests and ten actual parser tests. A further actual-image proposal fixture reproduces and verifies the fix for distinct series-run/collected-issue volumes; exact ownership and second-pass idempotence pass for the combined `v2.v005` GN layout. Source lint found one unused test import, which was removed; the native regression suite and all current-head checks passed. PR #202 merged at `45622f31ed8574ce46705e810d18c79e6a8cac51`; local main and the authorized Gitea mirror are synchronized.
- Both independent snapshot reviews completed. Their first four findings were daemon recovery behind its own fence, incomplete-copy retries, explicit source-like group prefixes and annual release-volume loss; independent re-verification confirms those fixes. Follow-up review found two volume compatibility cases: year-based ComicInfo Volume and collected issue volume distinct from series run. Both have regression fixes. A further review found volume-like text within titles, edition labels or scanner credits; volume evidence now excludes those proven fields, with a regression test. The final collected-field parser also passed independent contract re-verification, without bypassing native identity guards. Final contract re-verification is complete: both independent reviewers report no remaining actionable findings or nits. Ambiguous arrivals now retain waiting reasons without starving eligible later publications.
- Examples remain disabled. Preparation, image module ownership, stack metadata, owning documentation and the specification register are updated. Existing Compose/environment/ingress contracts require no added mounts, ports, variables or privileges. Generated catalog/topology checks passed.
- The coordinating supplement chat confirmed Mylar reports post-processing active despite an empty live queue and no progress for fifteen minutes; the cause remains unproven. The supplement pass now has an explicit quiescent handoff: it stopped between publications, writer fences are clear and its temporary per-file backup directory is empty. Our queued read-only parser diagnostics completed and confirmed the collected-volume rejection; the post-processing health cause remains under investigation. After the safe pause, native health reports processing=false with the post-processing queue alive and empty. No persistent stale processing flag was established. The final supplement publication has a committed, cleaned native receipt; all 507 supplement commits are retained for proof. Parser/image gates and reviewed delivery are complete; matching main-image publication precedes the coordinated backup and rollout.
- Matching images are deployed and the naming policy is enabled. T017–T018 remain open for the isolated eligible bulk pass, exact archive/catalog/reader readiness evidence, coordinated deferral rebinding and cleanup. The user deferred additional reading-progress verification on 2026-10-03; retain existing implementation safeguards and backups, but do not block this live pass on an extra all-user progress audit.

- Coordination requires preserving the private repaired-file credit-deferral ledger across renames: its entries are exact paths. Rebind only through verified source/destination hashes and native naming receipts before resuming derived Tags.

- T016 backup evidence: matching main images were pulled. The fresh backup restored and hash-verified 7,236 application/intake files and five readable SQLite databases, with native counts 2,507 comics / 15,340 issues / 141 annuals. Four live environment references are backed up and restore-verified, including the unchanged Mylar environment symlink. Image pins were updated in place with naming initially disabled before the successful pilot. Komga and NZBGet remain running. The single-file pilot subsequently passed; its compact receipt is retained.

- Compatible live images run at merge `45622f31ed8574ce46705e810d18c79e6a8cac51`; initial disabled-policy runtime verification passed before policy activation. Runtime proof confirms xxhash 3.0.0, intact/readable native databases, all baseline native IDs preserved, counts unchanged and enabled workers alive. Civil War II #6 is a unique native owner and unique actual reader hash, READY with 29 pages; the bounded pilot has now passed.

- T016 live pilot is complete: Civil War II #6 became `Civil.War.II.006.(2016).cbz` with exact archive SHA/inode/attributes and native owner preserved; Komga is READY at 29 pages, and the completed receipt remains after temporary copies were removed. The private naming policy is enabled with batch size 1. The daemon and supplement batch remain paused for the isolated bulk pass. Additional reading-progress audit remains deferred by the user.

- T019 corrective source verification: 30 file-identity tests and seven renderer tests pass; both complete candidate image gates pass, including 178 worker tests with no skips and the actual native parser. Both independent reviewers cleared their findings after generic Edition and HC Omnibus regressions were added. Full local CI passed. Corrective delivery and live repair remain pending.
