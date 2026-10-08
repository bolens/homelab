# Archive repair validation

## Preconditions

Read the [contract](contracts/archive-repair.md), owning stack READMEs and feature 022/023 gates. Source checks are read-only. Actual adoption needs coordinated writers, measured consistent backup, independent restore and current reader/source custody evidence. Private diagnostics are not publication permission.

## Diagnostics

Run owning archive/native/worker tests once installed and `python scripts/sync-publication-reader.py --check`. Valid archives bypass classification; the supported defect reports a candidate; damaged/unsafe/stale inputs retain terminal refusal. Registry/catalog/owner failures must not classify. Output contains no private paths, content or grants.

## Owned acceptance

Isolated controls prove complete CRC/member/page/metadata/compressed-byte equality and source/stage/custody/owner/census bindings. Exercise late byte/mode/inode changes, mixed journals, rejected owners, lost responses and restarts. Real scoped repair waits for independent source review, actual selected-runtime checks and matching image acceptance; then compare native/reader state and repaired bytes against baseline before acknowledgement or cleanup.

## Repository checks

Run focused tests, `make validate` and appropriately broad `make ci-local` before reviewed delivery. Record optional-tool skips and distinguish source, image and live evidence in [tasks.md](tasks.md).
