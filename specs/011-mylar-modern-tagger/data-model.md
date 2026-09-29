# Data model

- ProcessResult: state `ok`, `failed`, `timed_out`, `unavailable`, or `output_limit`;
  optional exit code; bounded stdout/stderr bytes excluded from repr; no stored argv.
- MetadataOverrides: explicit integer Volume, paired StoryArc/StoryArcNumber and
  optional AgeRating. Missing values do not authorize clearing existing values.
- Reconciled ComicInfo: root ComicInfo, <=256 KiB UTF-8 XML, no DTD/entities;
  previous fields retained unless explicitly replaced. Unrecognized fields survive.
- TagReceipt v1: private opaque token, backend/version, source path/identity/hash,
  request digest, workspace identity, destination hash/identity, permissions,
  metadata outcome, state and cleanup completion. Secret arguments and supplied
  metadata are not persisted. Page/member verification occurs before publishing.
- Current publisher progression: staged -> publishing -> committed. Unchanged,
  failed, timed_out and unsupported are terminal outcomes. Restart at publishing
  reconciles both exchanged files' hashes and identities rather than repeating a
  write. Conflict retains copies and blocks a new operation on that source.
  Replaying cleaned, superseded history reports a conflict to that caller without
  turning historical success into a blocking active operation.
- Receipts and permanent lock files live in a private directory. Each new job
  streams receipt headers to check for unresolved source ownership; there is no
  lifetime operation quota. An indexed journal/retention policy may be added later
  without deleting unresolved receipts or silently reusing operation tokens.
- Future transport selection: `requests` default or `curl_discovery`; full
  `curl_stream` unavailable until its acceptance gate. Store independently of
  queue ordering and provider cooldown state.

- RecoveryResult: validated opaque token (empty for invalid names), typed outcome,
  optional verified metadata outcome. Busy jobs, malformed receipts and I/O errors
  are explicit blocking startup outcomes. The scanner never exposes file paths or
  raw exceptions and releases all job locks before yielding to its caller.
- Uncleaned committed receipts retain recovery copies if the source inode,
  permissions, links, extended attributes or displaced bytes/ownership changed.
  Schema/state validation happens before recovery can modify a journal or workspace.

- TagReceipt v2: separate NFS journal, `publication=rename-link-v1`, bounded base64
  ACL/user-attribute manifest. Other fields retain v1 meanings. The displaced
  original inode lives at `displaced.cbz`; candidate linking temporarily produces
  two candidate links, reconciled before commit. No v1 reader migration is implied.
