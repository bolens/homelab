# Data model

- ProcessResult: state `ok`, `failed`, `timed_out`, `unavailable`, or `output_limit`;
  optional exit code; bounded stdout/stderr bytes excluded from repr; no stored argv.
- MetadataOverrides: explicit integer Volume, paired StoryArc/StoryArcNumber and
  optional AgeRating. Missing values do not authorize clearing existing values.
- Reconciled ComicInfo: root ComicInfo, <=256 KiB UTF-8 XML, no DTD/entities;
  previous fields retained unless explicitly replaced. Unrecognized fields survive.
- Future TagReceipt v1: job token, backend/version, source identity/hash, staged hash,
  approved metadata fields, page/member manifest, destination identity/hash, state,
  sanitized reason and timestamps. Secret arguments never persisted.
- Future state progression: queued -> staged -> tagged -> verified -> publishing ->
  committed. Failed/time-out retains original. Restart at publishing reconciles
  hashes and records conflict rather than repeating an uncertain write.
- Future transport selection: `requests` default or `curl_discovery`; full
  `curl_stream` unavailable until its acceptance gate. Store independently of
  queue ordering and provider cooldown state.
