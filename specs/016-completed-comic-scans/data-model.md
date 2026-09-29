# Data model

`reader-scan.json`, version 1, records scope, known catalog identity/path keys, pending additions with stat identity/stable_since/ready_at/last_checked, and next_allowed/last_requested. Initial known set comes only from a successful read-only catalog snapshot. Deleted catalog entries are pruned. Pending work and request pacing survive restart. Unknown/corrupt state fails visibly instead of resetting.

`reader-scan-status.json` reports checked_at, pending, ready, last_requested and errors. No credentials or provider URLs are recorded. Existing normalizer worker.lock serializes the journal; media-writer protects readiness observation.

Transitions: new catalog path → waiting for stable tagged CBZ and completed receipts → ready → scan accepted. Failed requests retain pending work. A disappeared/changed/ineligible file invalidates ready state. First-baseline entries are not pending. Multiple owners of one path remain ineligible.
