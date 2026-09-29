# Research

- Decision: durable request over the existing primary-key API after rescan acceptance. Rationale: normalizer only calls `recheckFiles`; native recheckFiles has no structured success acknowledgment. Its JSON null is an established response, so catalog ownership is revalidated independently. Alternatives rejected: synchronous manual_metatag HTTP route, which returns no reliable outcome and uses fuzzy path fallback.
- Decision: exact issue/annual location under shared writer ownership. Rationale: pack extras and parent/release annual IDs make filename guessing unsafe.
- Decision: native PP worker idle poll. Rationale: avoids independent tagging threads and search-worker delays, preserves native shutdown behavior. Downloads retain priority.
- Decision: Modern only, missing ComicInfo only. Rationale: Modern supplies verified in-place publication receipts; Legacy returns staging paths with a different lifecycle. Unsupported settings remain visibly pending and never silently select Modern.
- Decision: stored per-attempt publication token and recover before file-hash check. Rationale: committed metadata changes the conversion digest and must not be mistaken for foreign modification after restart.
- Decision: producer acknowledgment only on versioned identity match. Rationale: HTTP 200 and old API failure responses are not durable admission proof.
- Decision: retain small terminal identities. Rationale: pruning them would permit old conversion receipt replay. Display is bounded independently.

Research inspected native queue source and the existing tagger, workflow, normalizer and publication modules at base 97a7f524. Read-only delegated research confirmed lock, manual-route and retry hazards. No unresolved design questions.

- Decision: optional `mylar.refresh_reader_after_tagging`, false by default. The installed reader scans on a schedule, so file watching cannot prove prompt metadata display. Use POST `/api/v1/books/{bookId}/analyze`: Komga 1.27.1 caches archive entries in `media.files`, and its ComicInfo provider ignores XML absent from that cache. Successful reanalysis schedules metadata import. Live acceptance superseded the initial metadata-refresh-only decision. Persist a pending follow-up after admission, poll the existing idempotent request for completion, and retain the receipt after an ambiguous refresh response. Do not restart or alter the reader.
