# Tasks: Converted comic tagging

## Setup and foundation

- [x] T001 Record scope, ownership and acceptance in specs/012-converted-comic-tagging/spec.md and plan.md.
- [x] T002 Add persistent token and automatic in-place settings regression coverage in stacks/mylar3/config/test_tagger_native.py, then implement in tagger_native.py and tagger_service.py.

## US1: Fill missing metadata after conversion

Independent test: one verified converted CBZ with a unique catalog path gains metadata and retains all other archive bytes.

- [x] T003 [US1] Add admission, exact identity, annual, settings, duplicate and stale-file fixtures in stacks/mylar3/config/test_converted_tagging.py. Enforce version 1, payload at most 8192 UTF-8 bytes, path at most 4096 characters, and 64 lowercase hexadecimal digest characters.
- [x] T004 [US1] Implement durable admission and serial processing in stacks/mylar3/config/converted_tagging.py with 6 attempts, 24-hour catalog waits and 32 hexadecimal publication tokens.
- [x] T005 [US1] Integrate checked primary-key API and idle PP polling in stacks/mylar3/config/patch_converted_tagging.py and apply_patches.py.
- [x] T006 [US1] Test and implement opt-in handoff and independently optional durable reader metadata refresh after rescan in stacks/komga/normalizer/normalize.py and notification isolation in writer_cycle.py.

## US2: Recovery and visible status

Independent test: restart after publication and duplicate delivery never trigger another publication; status survives restart.

- [x] T007 [US2] Add restart/publication/retry fixtures in stacks/mylar3/config/test_converted_tagging.py.
- [x] T008 [US2] Expose bounded escaped status in stacks/mylar3/config/pp_monitor.py and post_processing.html.

## Validation and delivery

- [x] T009 Update both stack README, preparation, example and metadata contracts, and register tests in stacks/mylar3/config/verify_image.py.
- [x] T010 Run focused and image gates, repository checks and review; record results in specs/012-converted-comic-tagging/validation.md.
- [ ] T011 Merge reviewed changes, verify published images, and record delivery in specs/012-converted-comic-tagging/validation.md.
- [ ] T012 Deploy consumer then producer with verified scoped backups, selected-file canary, preservation and protected-service uptime checks; record private evidence and clean operation backups.

## Dependencies and strategy

T001 -> T002 -> T003/T004 -> T005 -> T006 -> T007/T008 -> T009 -> T010 -> T011 -> T012.
Implement US1 first, then recovery visibility before rollout. Independent producer and consumer fixture runs may execute in parallel; code edits remain sequential. All task entries have IDs and concrete source/evidence paths. Five US1 tasks, two US2 tasks, five foundation/delivery tasks.
