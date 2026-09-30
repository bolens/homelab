# Tasks: PDF comic normalization

Status updated 2026-09-29. Implementation and isolated verification are distinct
from live activation; no live deployment or import is claimed below.

- [x] T001 Inspect source contracts, tools and cached-file eligibility; write preservation requirements and plan.
  Evidence: existing converter has no PDF renderer; both inactive cached art books
  have unique catalog identities. PDF partial suffixes stay excluded from automation.
- [x] T002 Implement bounded PDF derivative adapter with durable source retention and real rendering regressions.
  Evidence: Poppler/Pillow rendering, ordered PNG inventories, verified original
  and cache digests, dimension/page/byte/time/storage limits. Fixtures cover
  corrupt/encrypted policy, rotation, source mutation, disabled mode, collision,
  cache tampering, interrupted commit and prepared-copy retry.
- [x] T003 Integrate library, cached single and pack conversion/import with opt-in behavior and recovery tests.
  Evidence: guarded publication and source-preserving import; rendering from the
  saved PDF runs after the media writer lock is released. Guided confirmation
  waits before claiming. Disabled PDF policy preserves page archives containing
  PDF extras. Mylar accepts structurally valid PDF transfers and preserves PDF
  catalog ownership through converted tagging and rescans.
- [x] T004 Update tracked contracts, generated catalog and run final focused/full validation.
  Evidence: all affected Mylar/Komga contracts updated, generators run, strict
  `make ci-local` passed. Final normalizer image gate: 144 tests, no skips.
  Mylar image gate includes native patch application, modern runtime, actual PDF
  transfers, converted catalog/rescan and archive-preference tests.
- [ ] T005 Complete independent review, current-head CI, merge and GHCR publication.
  Two focused reviewers examined native search/callers and preservation/recovery.
  Findings addressed: PDF catalog mapping, disabled pack behavior, atomic prepared
  copies, guided confirmations, expanded-output storage sizing, maximum-page
  workspace reservation, and fallback retention on a later search timeout.
  Both reviewers closed their findings on the final tree. Remote CI, merge and
  publication remain pending.
- [ ] T006 Deploy with verified scoped backup, isolated restore and rollback readiness.
  Back up affected Mylar/normalizer state and configuration, plus only affected
  media. Keep Komga/NZBGet/Kuma running; deploy Mylar before enabling worker PDF
  support. Keep each service running during the other service's update.
- [ ] T007 Verify live imports, tagging/reader outcomes and uninterrupted unrelated services; sync mirror and clean operation backups/branch.
  Requires actual post-deployment evidence. Preserve original PDFs in durable
  normalizer recovery state, distinct from disposable operation backups.
- [x] T008 Verify complete cached-book rendering and representative visual samples.
  Evidence: isolated production-limited container decoded and verified every page:
  Tomb Raider 97 pages, 802605477-byte CBZ, 55.74 seconds; Horizon 52 pages,
  302133956-byte CBZ, 30.97 seconds. Both source checksums unchanged. Cover,
  middle and final page images visually inspected; spreads and layout intact.
  Horizon's retained partial copy is structurally complete; only explicit inactive
  recovery may adopt it. No automatic promotion of partial downloads.
- [x] T009 Prefer CBZ/CBR alternatives while retaining PDF fallback and existing ordering.
  Implementation: declared native archives rank before unknown formats and PDF;
  native identity/quality and pack checks retained; queue date/kind ordering
  unchanged. Bounded lookahead retains a verified fallback if a later page fails.
  Five focused preference tests pass; native image gate and independent reviewer
  confirm field propagation, matching, fallback and COMICINFO ordering.

## Edition acceptance

The cached Horizon PDF renders completely but is the short Dark Horse digital art
book (52 PDF pages including covers), not Mylar's tracked Titan hardcover. Retain
it as a related extra without satisfying or applying the hardcover issue metadata.
The Tomb Raider PDF is the matching Titan art book (97 scanned spreads/pages).
This distinction must be verified during T007; filename-embedded issue IDs alone
do not override discovered contrary edition evidence.

## Operational status

System authentication restored. No live service has been restarted and no library
file has been changed by this feature yet. Live activation and both outcomes remain
open until preservation, tagging/reader and service-uptime checks pass.
