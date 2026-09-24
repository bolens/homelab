# Implementation plan

Extend the existing Mylar startup-patch contract with queue control and transfer helpers.
Persist control state under Mylar's existing configuration volume. Reuse existing web
session authentication and primary-key API authentication. Extend the Komga maintenance
worker to publish bounded, sanitized import-problem reports through that API.

Keep ports, networks, image pins, credentials, privileges, and library mounts unchanged.
Document defaults and state ownership in the stack READMEs and metadata. Add no automatic
service restart policy. Preserve original partials when a server cannot resume safely.

Use source-derived worker, API, and page tests plus real archive and interrupted-transfer
fixtures. Include them in the offline pinned-image gate. Verify search query generation
and run bounded read-only provider probes. Run focused tests followed by `make validate`.

Before deployment, stop affected workers, capture application records and library hashes,
back up affected configuration and persistent state, restore to an isolated location,
and verify hashes and database readability. Preserve the prior patch files for rollback.
After deployment verify automatic queue restoration, UI/API behavior, progress, archive
integrity, original records and files, and Kuma health. Roll back on loss or corruption.
Retain backups if verification is inconclusive; remove temporary copies only after success.
