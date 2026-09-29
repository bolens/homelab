# Tasks: Completed comic reader scans

## Foundation

- [x] T001 Record readiness, policy, state, API and rollout contracts in specs/016-completed-comic-scans.
- [x] T002 Implement validated durable policy and catalog baseline in stacks/komga/normalizer/reader_scan.py.

## US1: Completed additions

- [x] T003 Add bounded CBZ metadata/readiness checks, pending-receipt gates and exact library targeting in reader_scan.py.
- [x] T004 Integrate under-lock observation and after-lock dispatch in writer_cycle.py and normalizer lifecycle/health.

## US2: Batching and recovery

- [x] T005 Implement batch/tail/minimum-interval pacing, restart, partial acknowledgment and failure retention.
- [x] T006 Verify acceptance cases in test_reader_scan.py and test_writer_cycle.py; run full image and repository gates.

## Delivery

- [ ] T007 Update owning README, example config, preparation and image/metadata contracts. Review diff and required checks, merge and publish GHCR.
- [ ] T008 Verify backup/isolated restore, deploy only normalizer, enable config, prove health/scan acknowledgment/data preservation and protected uptime; remove operation backups and synchronize remotes/branches.
