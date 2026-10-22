# Archive repair validation

## Preconditions

Read the [contract](contracts/archive-repair.md), owning stack READMEs and feature 022/023 gates. Source checks are read-only. Actual adoption needs coordinated writers, measured consistent backup, independent restore and current reader/source custody evidence. Private diagnostics are not publication permission.

## Diagnostics

Run owning archive/native/worker tests once installed and `python scripts/sync-publication-reader.py --check`. Valid archives bypass classification; the supported defect reports a candidate; damaged/unsafe/stale inputs retain terminal refusal. Registry/catalog/owner failures must not classify. Output contains no private paths, content or grants.

## Owned acceptance

Isolated controls prove complete CRC/member/page/metadata/compressed-byte equality and source/stage/custody/owner/census bindings. Exercise late byte/mode/inode changes, mixed journals, rejected owners, lost responses and restarts. Real scoped repair waits for independent source review, actual selected-runtime checks and matching image acceptance; then compare native/reader state and repaired bytes against baseline before acknowledgement or cleanup.

## NFS publication checks

The prospective plan13 purpose requires one admitted private common root with
exactly library and retention children on the same actual NFS4 mount instance.
Separate library/retention binds are insufficient even when device numbers match.
Do not replace this admission with a writable shared ancestor. Reader shutdown,
cooperative Writer exclusion and absence of independent name mutators are
required throughout the transition; the contract states the syscall boundary.

Run the owning `test_publication_archive_nfs.py` component suite and the isolated
`run_reader_recovery_controls.py` collection from `stacks/mylar3/config/`.
Their local filesystem/schema controls do not establish genuine Parent/Birth or
NFS execution. The [scenario prerequisites](../../stacks/mylar3/config/reader_recovery/GENUINE-ARCHIVE-SCENARIO.md)
describe the maintained bootstrap, current-role/active-input assembler and checked
plan13 producer. The isolated bootstrap and component controls exist; connected
Parent/factory/NFS/terminal acceptance remains open in [tasks.md](tasks.md). The
legacy exchange probe is diagnostic only and is not the new protocol's admission
gate.

## Repository checks

Run focused tests, `make validate` and appropriately broad `make ci-local` before reviewed delivery. Record optional-tool skips and distinguish source, image and live evidence in [tasks.md](tasks.md).
