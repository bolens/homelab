# Decisions

- Reuse converted-tag admission for missing tags. Its digest-bound queue already verifies exact catalog ownership, Modern settings and publication recovery. A separate background tagger would duplicate ownership.
- Reuse v2 NFS publication for nested repair. An ad-hoc in-place ZIP rewrite would lose crash recovery. Existing receipts can recover the new operation without knowing how candidate XML was generated.
- Keep strict default archive inspection. Nested metadata is accepted only by the repair path, and identity conflicts fail before publication.
- Reuse Activity policy controls and the post-processing monitor. No new page or authentication surface is needed.
- Bound traversal with a durable catalog cursor and per-file stat identity cache. Full-library hashing at startup would repeat the earlier performance problem.
