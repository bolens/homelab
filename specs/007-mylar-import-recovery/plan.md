# Plan: Automatic import recovery

Use the existing Komga maintenance cycle and primary-key Mylar API. Keep quarantine
release matching separate: recovery matching must not authorize failed-release
blacklisting. Add a bounded read-only matcher and durable recovery receipts, copy
one validated CBZ/CBR to an isolated DDL-cache staging directory, and submit its
explicit issue ID through native forceProcess. Preserve the original download.

Configure the Mylar-side cache path explicitly because container mount paths differ.
Do not add mounts, ports, networks, privileges, credentials, or dependencies. Update
normalizer configuration example, Mylar report labels, stack documentation and metadata.

Run matcher and interruption tests, existing image/normalizer gates, then make validate.
Before live updates, finish pending feature006 and wide-layout verification, back up
configuration/state with isolated restore verification, inspect current unmatched
records, then enable recovery and verify one end-to-end import. Retain backups for
inconclusive checks; rollback if data is lost or corrupted; remove temporary backups
only after successful verification. Live authentication is currently pending.

Constitution: portable defaults, explicit enablement, no added exposure, source
preservation and separate deployment authorization meet the existing constraints.
