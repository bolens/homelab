# Tasks: Modern tagger throughput

## Setup and foundation

- [x] T001 Record the measured baseline and safety requirements in specs/013-modern-tagger-throughput/spec.md and research.md.
- [x] T002 Add cache isolation, expiry, bounds and no-renewal regressions in stacks/mylar3/config/test_tagger_volume_cache.py.

## US1: Reuse fresh volume information

Independent test: two fresh issue lookups make three provider requests with unchanged resulting metadata.

- [x] T003 [US1] Implement a cache with at most 64 entries, 16 KiB per entry, and a non-sliding 300-second deadline in stacks/mylar3/config/tagger_volume_cache.py.
- [x] T004 [US1] Extend the private worker protocol and validated cache handoff in stacks/mylar3/config/tagger_lookup.py.
- [x] T005 [US1] Verify real child-process reuse, expiry during issue lookup, wrong identities, credential context and failed responses in stacks/mylar3/config/test_tagger_lookup.py.
- [x] T006 [US1] Register the module and tests in stacks/mylar3/config/install_tagger_service.py and verify_image.py.

## US2: Avoid copying preserved archives

Independent test: unchanged publication succeeds without archive staging and retains source/race/recovery checks.

- [x] T007 [US2] Add unchanged-path low-space, no-copy, source-race and recovery coverage in stacks/mylar3/config/test_tagger_adapter.py and test_tagger_nfs.py.
- [x] T008 [US2] Complete preserve-existing intent before archive staging in stacks/mylar3/config/tagger_adapter.py.

## Verification and delivery

- [x] T009 Record controlled before/after results and update stacks/mylar3/README.md and specs/013-modern-tagger-throughput/validation.md.
- [ ] T010 Run focused and image gates, required repository checks and independent reviews; record evidence in specs/013-modern-tagger-throughput/validation.md.
- [ ] T011 Merge through GitHub checks, verify published GHCR image and deploy only Mylar with verified backups and preservation checks; record evidence in specs/013-modern-tagger-throughput/validation.md.

## Dependencies and strategy

T001 -> T002 -> T003 -> T004 -> T005 -> T006. T007 -> T008 is independently testable. T006/T008 -> T009 -> T010 -> T011. Fixture runs for US1 and US2 may run independently; edits stay under one writer. Deliver both measured changes together after preservation review. All 11 entries have IDs and owning paths; US1 has four tasks and US2 has two.
