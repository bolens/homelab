# Research decisions

- Native search is serialized through `queues/search.py`; manual searches only collect results. Handoffs use automatic
  dispatch with a scoped Snatched-status bypass. Use a thread-local NZB-only scope and durable ownership, never
  global provider changes or a transient Wanted status. Recheck before downloader send.
- The current DDL worker reads status before its claim lock. Move the Downloading
  claim into the same locked boundary as handoff reservation. Queued/dispatching
  reservations survive restart and cannot be bypassed by native Retry controls.
- Downloader acceptance and local commits cannot be atomic. Persist dispatch intent
  first and keep uncertain outcomes for review instead of promising exactly-once I/O.
- Existing worker recovery preserves originals and writes receipts before processing.
  Guided selections reuse that path. Browser filenames are insufficient identifiers:
  worker-owned opaque tokens and current fingerprints bind proposals to files.
- Exact title/year aliases activate only after verified source-to-library equivalence,
  not after an API acknowledgement. Fuzzy ranking is only a suggestion to a human.
- Existing 15-minute health checks do not distinguish cooldown. Derive waits from
  actual pending rows; preserve dead-worker checks and a continuous-outage cap.
- Add intake hysteresis at search and dispatch boundaries. Sample configured roots
  and processing counts, not the complete comic library. Existing work can drain.
- Research used tracked patches and copied public source from deployed revision
  `92218acf935a51b62609330f45fa3d317000058a`; no runtime values enter this design.
