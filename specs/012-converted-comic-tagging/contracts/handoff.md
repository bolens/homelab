# Conversion handoff

POST the existing `/api` with primary `apikey`, `cmd=queueConvertedTag`, and JSON `conversion` containing exactly version=1, path and sha256. Successful response is the native success wrapper with data.version=1, data.key equal to the canonical request key, and data.phase. Admission writes the job before acknowledging. Conflicting or malformed inputs produce sanitized failure responses.

The producer calls `recheckFiles` first and preserves its pending receipt until strict handoff acknowledgment. Requests happen only outside shared writer ownership after conversions clear. Each notification failure is isolated. Opt-in `mylar.tag_converted=true` requires nonempty writer_state. Existing default remains rescan only.

Post-processing status adds `converted_tagging`, a bounded array of name, phase, reason, attempts, updated_at and sanitized IDs. UI renders all strings as text. No raw paths or tokens are returned. This table is separate from native download import status.

With `mylar.refresh_reader_after_tagging=true`, admission also persists mylar_tag_pending in the conversion receipt. Polling repeats only queueConvertedTag, never recheckFiles. Completed tagging submits a Komga metadata refresh for replacement_id, then persists the accepted request. Review does not trigger refresh. Disabled settings clear pending reader notifications. Uncertain requests retry without repeating metadata publication.
