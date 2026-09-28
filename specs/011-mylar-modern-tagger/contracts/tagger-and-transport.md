# Compatibility contracts

The first increment exposes internal pure helpers only. It does not add a UI choice
or change the active tagger/transport.

`tagger_runtime.run(argv, cwd, timeout, max_output)` accepts an argument sequence,
never a shell command. It returns bounded output and a typed state. It does not
inspect or replace archives. Both version and tagging processes use this boundary.
Callers must not log argv or raw output. Timeouts kill the process group and reap the direct child. The real-CLI gate must
prove that the trusted CLI does not detach children into other sessions. Otherwise
stronger containment is required before activation.

`tagger_metadata.reconcile(original, tagged, updates, replace_fields)` accepts bounded
ComicInfo bytes. Existing fields survive unless their names appear in replace_fields
or updates. It neither reads archives nor changes files. Updates are explicit writes,
not inferred deletion. Preserve full page metadata when pages are unchanged. StoryArc and StoryArcNumber
are one replacement group. A partial original name never borrows an unrelated
tagged number; partial explicit replacement or mismatched numbered lists is rejected.

The legacy adapter retains cmtagmylar.run's path/sentinel return contract. Modern
manual tagging uses an explicit `mylar.tagger_handoff.Published` result; automatic
routing must continue to supply a verified disposable path. The observer understands
typed results, but no native producer selects modern tagging yet.
One adapter owns replacement. Modern backend does not convert or delete originals.
Conversion-only and non-ZIP routes must be proved before native activation.

`tagger_adapter.Publisher.tag(source, metadata, token=...)` is an inactive internal
CBZ operation. It replaces a source only after staged verification, using Linux
atomic exchange to retain the displaced file until commit verification. Unsupported
filesystems have no weaker fallback. The caller must exclude non-cooperating writers;
an observed race keeps recovery copies and never reports success. Hardlinks and
extended attributes/ACLs are unsupported. `recover(token)` reconciles a durable
intent without repeating the CLI. Same-token/different-request calls conflict;
separate token and source locks serialize overlapping work. Raw child output and
file paths never appear in the returned `Result`. No native caller uses this API yet.

Future discovery session exposes the current requests get/post/context lifetime and
exception expectations. Provider resolution and archive transfers are separate
choices. No double retry layer, extra cooldown mutation, automatic fallback, or
unbounded queue is acceptable. Public workflow routes retain existing authentication
and CSRF. Selection is validated server-side and shown with accurate availability.

`Publisher.recover_pending()` streams sanitized `RecoveryResult(token, state,
metadata)` records. It does not wait for token/source locks or hash cleaned history.
Callers must exhaust the iterator before admitting modern work and keep admission
closed on `busy`, `conflict`, `invalid_journal` or `io_error`. Malformed receipt names
return an empty token, never a path/name. Unexpected receipts remain untouched; one
invalid receipt does not prevent reconciliation of other valid pending jobs. This
API is not yet called from native startup.

`mylar.tagger_handoff.capture(publisher, token)` reconciles a receipt and checks its
cleaned outcome, current bytes, inode, permissions and expected source before
creating an in-place result. Paths and digests are excluded from repr. Manual
callers reverify the exact expected source before bypassing copy/delete and rescanning.
All four automatic calls reject every non-string result before placement. Unknown
or foreign typed results fail closed. Producers and consumers must import the same
canonical native module; the final image has no standalone handoff module copy.

`mylar.tagger_service.Service` requires a private cache and a global media-writer
coordinator. Every admitted job exhausts pending publication recovery under that
coordinator. Manual success returns canonical `Published`; automatic success returns
a disposable path and preserves the download source. Automatic failures remain the
literal `fail` string with a typed reason for the observer. No-overwrite on existing
ComicInfo skips lookup, overrides and CLI work. Unsupported modes fail closed.
The exact backend selector never retries through legacy after a modern failure.
No native entry point or setting calls this service yet. Failed/uncertain staging
remains private, pending coordinated native cleanup and startup ownership.

`tagger_lookup.lookup` keeps credentials in a private temporary file, never argv,
and bounds the child to 45 seconds and 64 KiB output. HTTP responses are limited to
1 MiB, reject redirects, and use explicit fields. Issue, linked volume and expected
volume identities must agree. The caller supplies the actual annual release volume
when applicable. Provider requests wait the configured interval before each request.
Only fields explicitly returned by the provider may replace existing fields.
