# Implementation plan

Add `pp_monitor.py`, a bounded in-memory observer around the actual
`PostProcessor.Process` method. The native queue coordinator can return before its
background thread finishes, so observing only `Process.post_process` would report
false completion. Preserve return values and exceptions, and prevent observer
failures from altering processing. Never inspect or publish raw log messages.

Snapshot the waiting queue under its mutex without consuming entries. Combine
worker availability and processing-lock state with sanitized active observations,
a bounded recent-attempt history, and recent confirmed imports from the database.
Observations reset on restart and the page explains that lifetime. No new persistent
state, credentials, ports, networks, mounts, privileges, or concurrency settings.

Extend the source-checked startup hook with a dedicated patch. Add authenticated
`postProcessing` and `postProcessingStatus` routes through the existing WebInterface
authentication. Add links from Manage, DDL Queue Management, and Import problems.
Use the existing jQuery UI and DataTables assets. Poll without overlapping requests,
preserve table navigation, and show stale/error states without discarding the last
successful snapshot. Escape all dynamic text and display only safe basenames and
numeric identifiers.

Validate against the pinned image with worker lifecycle, exception, queue
preservation, privacy, bounded-history, and source-drift fixtures. Verify real
browser navigation, rendered styling, automatic refresh, failed refresh, and login
requirements. Run focused checks, then `make validate`.

For deployment, wait for idle post-processing, stop affected workers, back up Mylar
configuration/state and compatible public patch sources, restore to an isolated
location, and verify hashes and database integrity. Record application IDs and
library metadata. Deploy the same pinned image with the new hook, verify worker
health and page behavior, and compare application IDs and existing library files.
Roll back on data loss or corruption. Keep backups if verification is inconclusive,
and remove temporary backups after successful verification.

Observe `cmtagmylar.run` without altering its arguments, return, or exceptions.
Inspect bounded archive headers and ZIP metadata blocks before and after successful
tagging, keeping only fingerprints and readable outcomes. Never expose metadata
contents. RAR metadata that was not inspected remains explicitly unknown.

Extend the existing authenticated maintenance-report API with an optional bounded
conversion summary. The worker publishes sanitized names, original/output format,
and receipt phase from existing verified normalizer jobs. Store this small report
privately in the existing Mylar data directory and mark missing/stale reports.
No new mount or credentials. Back up this state and normalizer state with the
application before deploying the coordinated changes.
